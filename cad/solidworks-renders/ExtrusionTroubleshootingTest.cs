using System;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace SolidWorksRenders
{
    /// <summary>
    /// Test case to reproduce and demonstrate the CheckFeatureUse troubleshooting technique
    /// from the learning: troubleshooting-extrusion-failures.md
    ///
    /// This creates two sketches:
    /// 1. A self-intersecting bowtie sketch (will fail extrusion)
    /// 2. A valid rectangle sketch (will succeed)
    ///
    /// It demonstrates how to use ISketch.CheckFeatureUse() to diagnose WHY extrusions fail.
    /// </summary>
    public class ExtrusionTroubleshootingTest : IPartCreator
    {
        private readonly ISldWorks _swApp;

        public string PartName => "Extrusion Troubleshooting Test";
        public string FileName => "extrusion-troubleshooting-test.SLDPRT";

        public ExtrusionTroubleshootingTest(ISldWorks swApp)
        {
            _swApp = swApp ?? throw new ArgumentNullException(nameof(swApp));
        }

        public IModelDoc2 CreatePart()
        {
            // Create new part document
            IModelDoc2 doc = (IModelDoc2)_swApp.NewDocument(
                TemplateName: _swApp.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplatePart),
                PaperSize: 0,
                Width: 0,
                Height: 0);

            if (doc == null)
            {
                throw new InvalidOperationException("Failed to create new part document");
            }

            Console.WriteLine("\n=== TEST 1: Self-Intersecting Sketch (Expected to Fail) ===\n");

            // Test 1: Create self-intersecting bowtie sketch
            CreateSelfIntersectingSketch(doc);

            // Try to extrude it
            bool success = doc.Extension.SelectByID2(
                Name: "Sketch1",
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!success)
            {
                Console.WriteLine("ERROR: Failed to select Sketch1");
                return doc;
            }

            IFeature? feature = doc.FeatureManager.FeatureExtrusion3(
                Sd: true,                                          // Single direction
                Flip: false,                                       // Don't flip side to cut
                Dir: false,                                        // Don't flip extrusion direction
                T1: (int)swEndConditions_e.swEndCondBlind,        // End condition for direction 1
                T2: (int)swEndConditions_e.swEndCondBlind,        // End condition for direction 2
                D1: 0.01,                                          // Depth in meters (10mm)
                D2: 0,                                             // Depth for direction 2
                Dchk1: false,                                      // Draft outward direction 1
                Dchk2: false,                                      // Draft outward direction 2
                Ddir1: false,                                      // Draft direction 1
                Ddir2: false,                                      // Draft direction 2
                Dang1: 0,                                          // Draft angle direction 1
                Dang2: 0,                                          // Draft angle direction 2
                OffsetReverse1: false,                             // Offset reverse direction 1
                OffsetReverse2: false,                             // Offset reverse direction 2
                TranslateSurface1: false,                          // Translate surface 1
                TranslateSurface2: false,                          // Translate surface 2
                Merge: false,                                      // Merge result
                UseFeatScope: false,                               // Use feature scope
                UseAutoSelect: false,                              // Use auto select
                T0: (int)swStartConditions_e.swStartSketchPlane,  // Start condition
                StartOffset: 0,                                    // Offset from sketch plane
                FlipStartOffset: false                             // Flip start offset direction
            );

            // CRITICAL: Use CheckFeatureUse to diagnose WHY it failed
            if (feature == null)
            {
                Console.WriteLine("✗ Extrusion returned NULL - diagnosing sketch...");
                DiagnoseSketch(doc, "Sketch1");
            }
            else
            {
                Console.WriteLine("✓ Feature created - checking for errors...");
                CheckFeatureErrors(feature);
            }

            Console.WriteLine("\n=== TEST 2: Valid Rectangle Sketch (Expected to Succeed) ===\n");

            // Test 2: Create valid rectangle sketch
            CreateValidSketch(doc);

            // Try to extrude it
            success = doc.Extension.SelectByID2(
                Name: "Sketch2",
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!success)
            {
                Console.WriteLine("ERROR: Failed to select Sketch2");
                return doc;
            }

            IFeature? feature2 = doc.FeatureManager.FeatureExtrusion3(
                Sd: true,                                          // Single direction
                Flip: false,                                       // Don't flip side to cut
                Dir: false,                                        // Don't flip extrusion direction
                T1: (int)swEndConditions_e.swEndCondBlind,        // End condition for direction 1
                T2: (int)swEndConditions_e.swEndCondBlind,        // End condition for direction 2
                D1: 0.01,                                          // Depth in meters (10mm)
                D2: 0,                                             // Depth for direction 2
                Dchk1: false,                                      // Draft outward direction 1
                Dchk2: false,                                      // Draft outward direction 2
                Ddir1: false,                                      // Draft direction 1
                Ddir2: false,                                      // Draft direction 2
                Dang1: 0,                                          // Draft angle direction 1
                Dang2: 0,                                          // Draft angle direction 2
                OffsetReverse1: false,                             // Offset reverse direction 1
                OffsetReverse2: false,                             // Offset reverse direction 2
                TranslateSurface1: false,                          // Translate surface 1
                TranslateSurface2: false,                          // Translate surface 2
                Merge: false,                                      // Merge result
                UseFeatScope: false,                               // Use feature scope
                UseAutoSelect: false,                              // Use auto select
                T0: (int)swStartConditions_e.swStartSketchPlane,  // Start condition
                StartOffset: 0,                                    // Offset from sketch plane
                FlipStartOffset: false                             // Flip start offset direction
            );

            if (feature2 == null)
            {
                Console.WriteLine("✗ Extrusion returned NULL - diagnosing sketch...");
                DiagnoseSketch(doc, "Sketch2");
            }
            else
            {
                Console.WriteLine("✓ Feature created - checking for errors...");
                CheckFeatureErrors(feature2);
            }

            return doc;
        }

        /// <summary>
        /// Creates a self-intersecting bowtie sketch that will fail extrusion
        /// This creates an X-shaped pattern as shown in the learning document
        /// </summary>
        private void CreateSelfIntersectingSketch(IModelDoc2 doc)
        {
            // Select Front Plane
            bool success = doc.Extension.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!success)
            {
                throw new Exception("Failed to select Front Plane");
            }

            doc.SketchManager.InsertSketch(true);

            // Creates an X shape (self-intersecting bowtie)
            doc.SketchManager.CreateLine(0, 0, 0, 0.05, 0.05, 0);       // Diagonal /
            doc.SketchManager.CreateLine(0.05, 0.05, 0, 0, 0.05, 0);    // Top horizontal
            doc.SketchManager.CreateLine(0, 0.05, 0, 0.05, 0, 0);       // Diagonal \
            doc.SketchManager.CreateLine(0.05, 0, 0, 0, 0, 0);          // Bottom horizontal

            doc.SketchManager.InsertSketch(true); // Exit sketch

            Console.WriteLine("Created self-intersecting bowtie sketch (Sketch1)");
        }

        /// <summary>
        /// Creates a valid rectangle sketch that will succeed extrusion
        /// </summary>
        private void CreateValidSketch(IModelDoc2 doc)
        {
            // Select Front Plane
            bool success = doc.Extension.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!success)
            {
                throw new Exception("Failed to select Front Plane for Sketch2");
            }

            doc.SketchManager.InsertSketch(true);

            // Create a simple rectangle centered at origin
            doc.SketchManager.CreateCenterRectangle(0, 0, 0, 0.025, 0.025, 0);

            doc.SketchManager.InsertSketch(true); // Exit sketch

            Console.WriteLine("Created valid rectangle sketch (Sketch2)");
        }

        /// <summary>
        /// THE KEY METHOD: Uses ISketch.CheckFeatureUse() to diagnose WHY a sketch can't be extruded
        /// This is the primary technique from the learning document
        /// </summary>
        private void DiagnoseSketch(IModelDoc2 doc, string sketchName)
        {
            // Select and get the sketch
            bool success = doc.Extension.SelectByID2(
                Name: sketchName,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!success)
            {
                Console.WriteLine($"ERROR: Failed to select {sketchName} for diagnosis");
                return;
            }

            ISelectionMgr swSelMgr = (ISelectionMgr)doc.SelectionManager;
            IFeature sketchFeat = (IFeature)swSelMgr.GetSelectedObject6(1, -1);

            if (sketchFeat == null)
            {
                Console.WriteLine($"ERROR: Failed to get feature for {sketchName}");
                return;
            }

            ISketch sketch = (ISketch)sketchFeat.GetSpecificFeature2();

            if (sketch == null)
            {
                Console.WriteLine($"ERROR: Failed to get sketch interface for {sketchName}");
                return;
            }

            // THE KEY METHOD - CheckFeatureUse diagnoses the problem
            int openCount = 0;
            int closedCount = 0;
            int checkStatus = sketch.CheckFeatureUse(
                (int)swSketchCheckFeatureProfileUsage_e.swSketchCheckFeature_BASEEXTRUDE,
                ref openCount,
                ref closedCount
            );

            Console.WriteLine($"Sketch Check Status: {checkStatus} ({(swSketchCheckFeatureStatus_e)checkStatus})");
            Console.WriteLine($"Open Contours: {openCount}");
            Console.WriteLine($"Closed Contours: {closedCount}");

            // Check for self-intersecting status codes
            if (checkStatus == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_CturXCtur ||
                checkStatus == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_EntXSelf ||
                checkStatus == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_EntXEnt)
            {
                Console.WriteLine("DIAGNOSIS: Self-intersecting geometry detected");
                Console.WriteLine($"Specific issue: {(swSketchCheckFeatureStatus_e)checkStatus}");
            }
            else if (checkStatus == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_OK)
            {
                Console.WriteLine("DIAGNOSIS: Sketch is valid for extrusion");
            }
            else
            {
                Console.WriteLine($"DIAGNOSIS: Other issue detected - {(swSketchCheckFeatureStatus_e)checkStatus}");
            }
        }

        /// <summary>
        /// Secondary method: Uses IFeature.GetErrorCode2() when feature exists
        /// This is less useful than CheckFeatureUse but shown for completeness
        /// </summary>
        private void CheckFeatureErrors(IFeature feature)
        {
            bool isWarning = false;
            int errorCode = feature.GetErrorCode2(out isWarning);

            if (errorCode == 0)
            {
                Console.WriteLine("✓ Extrusion succeeded with no errors");
            }
            else if (errorCode == (int)swFeatureError_e.swFeatureErrorSketchContainsSelfIntersectingContour)
            {
                Console.WriteLine("DIAGNOSIS: Sketch contains self-intersecting contour");
                Console.WriteLine($"Error code: {errorCode}");
            }
            else
            {
                Console.WriteLine($"✗ Feature has error code: {errorCode}");
                Console.WriteLine($"Is warning: {isWarning}");
            }
        }

        public void PrintPartDetails()
        {
            Console.WriteLine("\nThis test demonstrates the CheckFeatureUse troubleshooting technique:");
            Console.WriteLine("- Test 1 creates a self-intersecting bowtie that fails extrusion");
            Console.WriteLine("- Test 2 creates a valid rectangle that succeeds");
            Console.WriteLine("- CheckFeatureUse() diagnoses WHY sketches can't be extruded");
        }
    }
}
