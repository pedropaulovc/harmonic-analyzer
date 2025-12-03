using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System;

namespace SolidWorksRenders
{
    /// <summary>
    /// Creates an amplitude bar - vertical rod with notches at top and bottom.
    /// Translated from amplitude-bar.kcl
    ///
    /// Features a 32" vertical bar (0.25" x 0.25") with:
    /// - Bottom notch: 0.125" wide x 0.09375" (3/32") tall
    /// - Top notch: 0.125" wide x 0.5" tall
    /// Both notches are centered on the bar width.
    /// </summary>
    public class AmplitudeBar : IPart
    {
        public string PartName => "Amplitude Bar";
        public string FileName => "amplitude-bar.sldprt";
        public string Description => "Vertical 32\" rod with top and bottom notches";

        // Bar dimensions (in inches, converted to meters for SolidWorks API)
        private const double BarLength = 32.0 * 0.0254;        // 32 inches
        private const double BarWidth = 0.25 * 0.0254;         // 0.25 inches
        private const double BarDepth = 0.25 * 0.0254;         // 0.25 inches

        // Bottom notch dimensions
        private const double BottomNotchWidth = 0.125 * 0.0254;     // 0.125 inches
        private const double BottomNotchHeight = 0.09375 * 0.0254;  // 3/32 inches

        // Top notch dimensions
        private const double TopNotchWidth = 0.125 * 0.0254;   // 0.125 inches
        private const double TopNotchHeight = 0.5 * 0.0254;    // 0.5 inches

        // Calculated parameters - offsets to center the notches on the bar
        private readonly double leftNotchOffset;
        private readonly double rightNotchOffset;

        private ISldWorks swApp;

        public AmplitudeBar(ISldWorks solidWorksApp)
        {
            swApp = solidWorksApp ?? throw new ArgumentNullException(nameof(solidWorksApp));

            // Calculate notch offsets to center them on the bar
            leftNotchOffset = (BarWidth - BottomNotchWidth) / 2;
            rightNotchOffset = (BarWidth - TopNotchWidth) / 2;
        }

        /// <summary>
        /// Creates the amplitude bar part
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

            // Create the bar profile with notches and extrude
            IFeature barFeature = CreateBarProfile(swModel);

            // Rebuild the model
            swModel.ForceRebuild3(true);

            return swModel;
        }

        /// <summary>
        /// Creates the bar profile with bottom and top notches, then extrudes.
        /// The profile traces around both centered notches:
        ///   ##  ##
        ///   ##  ##
        ///   ##  ##
        ///   ######
        ///   ######
        ///   ######
        ///   ######
        ///   ######
        ///   ######
        ///   ######
        ///   ######
        ///   ######
        ///   ##  ##
        ///   ##  ##
        /// </summary>
        private IFeature CreateBarProfile(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select XZ Plane (Right Plane in SolidWorks) for the profile sketch
            // The KCL uses XZ plane (vertical plane)
            bool selected = swModelExt.SelectByID2(
                Name: "Right Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Right Plane");

            // Insert sketch on Right Plane
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Create the profile following the KCL path
            // Starting at [0, 0] and tracing the outline with bottom and top notches
            // The profile starts at bottom-left and traces clockwise

            // Start point at origin (bottom-left corner)
            double x = 0;
            double y = 0;

            // Line 1: Move right to start of bottom notch
            swSketchMgr.CreateLine(x, y, 0, x + leftNotchOffset, y, 0);
            x += leftNotchOffset;

            // Line 2: Move up for bottom notch height
            swSketchMgr.CreateLine(x, y, 0, x, y + BottomNotchHeight, 0);
            y += BottomNotchHeight;

            // Line 3: Move right across bottom notch
            swSketchMgr.CreateLine(x, y, 0, x + BottomNotchWidth, y, 0);
            x += BottomNotchWidth;

            // Line 4: Move down to base
            swSketchMgr.CreateLine(x, y, 0, x, y - BottomNotchHeight, 0);
            y -= BottomNotchHeight;

            // Line 5: Move right to right edge
            swSketchMgr.CreateLine(x, y, 0, x + leftNotchOffset, y, 0);
            x += leftNotchOffset;

            // Line 6: Move up the full bar length
            swSketchMgr.CreateLine(x, y, 0, x, y + BarLength, 0);
            y += BarLength;

            // Line 7: Move left to start of top notch
            swSketchMgr.CreateLine(x, y, 0, x - rightNotchOffset, y, 0);
            x -= rightNotchOffset;

            // Line 8: Move down for top notch height
            swSketchMgr.CreateLine(x, y, 0, x, y - TopNotchHeight, 0);
            y -= TopNotchHeight;

            // Line 9: Move left across top notch
            swSketchMgr.CreateLine(x, y, 0, x - TopNotchWidth, y, 0);
            x -= TopNotchWidth;

            // Line 10: Move up to top
            swSketchMgr.CreateLine(x, y, 0, x, y + TopNotchHeight, 0);
            y += TopNotchHeight;

            // Line 11: Move left to left edge
            swSketchMgr.CreateLine(x, y, 0, x - rightNotchOffset, y, 0);
            x -= rightNotchOffset;

            // Line 12: Close the profile - move down back to start
            swSketchMgr.CreateLine(x, y, 0, 0, 0, 0);

            // Exit sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Get the sketch name
            swModel.ForceRebuild3(false);
            IFeature barSketch = swModelExt.GetLastFeatureAdded();
            if (barSketch == null)
                throw new InvalidOperationException("Failed to get bar profile sketch");

            string sketchName = barSketch.Name;
            Console.WriteLine($"DEBUG: Bar profile sketch name: {sketchName}");

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
                throw new InvalidOperationException($"Failed to select bar profile sketch '{sketchName}' for extrusion");

            // Extrude the profile to create the 3D bar
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: true,                                          // Single direction
                Flip: false,                                       // Don't flip side to cut
                Dir: false,                                        // Don't flip extrusion direction
                T1: (int)swEndConditions_e.swEndCondBlind,        // Blind extrusion
                T2: (int)swEndConditions_e.swEndCondBlind,        // Not used for single direction
                D1: BarDepth,                                      // Extrusion depth (0.25")
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
                throw new InvalidOperationException("Failed to extrude bar profile");

            return extrudeFeature;
        }

        /// <summary>
        /// Prints amplitude bar part details
        /// </summary>
        public void PrintPartDetails()
        {
            Console.WriteLine("\nPart Details:");
            Console.WriteLine("- Bar dimensions: 32\" x 0.25\" x 0.25\"");
            Console.WriteLine("- Bottom notch: 0.125\" wide x 0.09375\" (3/32\") tall");
            Console.WriteLine("- Top notch: 0.125\" wide x 0.5\" tall");
            Console.WriteLine("- Both notches centered on bar width");
        }
    }
}
