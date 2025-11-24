using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System;
using System.Runtime.InteropServices;

namespace SelfIntersectingSketch
{
    class Program
    {
        static void Main(string[] args)
        {
            SldWorks swApp = null;
            try
            {
                Console.WriteLine("Connecting to SolidWorks...");
                try {
                    swApp = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
                } catch {
                    Console.WriteLine("Could not connect to running instance. Creating new instance...");
                    swApp = (SldWorks)Activator.CreateInstance(Type.GetTypeFromProgID("SldWorks.Application"));
                    swApp.Visible = true;
                }
                
                if (swApp == null) throw new Exception("Failed to connect to SolidWorks.");

                Console.WriteLine("Creating new part...");
                // Use default template or empty
                string template = swApp.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplatePart);
                ModelDoc2 doc = (ModelDoc2)swApp.NewDocument(template, 0, 0, 0);
                
                if (doc == null) {
                     Console.WriteLine("Default template not found, trying empty...");
                     doc = (ModelDoc2)swApp.NewDocument("", 0, 0, 0);
                }
                if (doc == null) throw new Exception("Failed to create document.");

                // Select Front Plane
                bool boolstatus = doc.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, false, 0, null, 0);
                if (!boolstatus) {
                     Console.WriteLine("Could not select Front Plane by name. Trying to find it...");
                     // Fallback logic could go here, but standard parts have Front Plane
                }

                Console.WriteLine("Creating self-intersecting sketch (bowtie shape)...");
                doc.SketchManager.InsertSketch(true);
                
                // Bowtie shape:
                // 1. (0,0) to (0.05, 0.05)
                doc.SketchManager.CreateLine(0, 0, 0, 0.05, 0.05, 0);
                
                // 2. (0.05, 0.05) to (0, 0.05)
                doc.SketchManager.CreateLine(0.05, 0.05, 0, 0, 0.05, 0);
                
                // 3. (0, 0.05) to (0.05, 0)
                doc.SketchManager.CreateLine(0, 0.05, 0, 0.05, 0, 0);
                
                // 4. (0.05, 0) to (0, 0)
                doc.SketchManager.CreateLine(0.05, 0, 0, 0, 0, 0);

                doc.SketchManager.InsertSketch(true); // Exit sketch

                Console.WriteLine("Attempting Extrusion...");
                
                // Select the sketch
                doc.Extension.SelectByID2("Sketch1", "SKETCH", 0, 0, 0, false, 0, null, 0);

                // Attempt Extrusion
                // FeatureExtrusion3 with named parameters
                IFeature feature = doc.FeatureManager.FeatureExtrusion3(
                    Sd: true,
                    Flip: false,
                    Dir: false,
                    T1: (int)swEndConditions_e.swEndCondBlind,
                    T2: 0,
                    D1: 0.01,
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
                    Merge: false,
                    UseFeatScope: false,
                    UseAutoSelect: true,
                    T0: (int)swStartConditions_e.swStartSketchPlane,
                    StartOffset: 0,
                    FlipStartOffset: false
                );


                if (feature != null)
                {
                    Console.WriteLine("Feature object returned.");
                    
                    bool isWarning = false;
                    int errorCode = feature.GetErrorCode2(out isWarning);
                    Console.WriteLine($"Feature Error Code: {errorCode}");
                    Console.WriteLine($"Is Warning: {isWarning}");

                    if (errorCode == (int)swFeatureError_e.swFeatureErrorSketchContainsSelfIntersectingContour)
                    {
                        Console.WriteLine("SUCCESS: Correctly identified self-intersecting contour error.");
                    }
                    else
                    {
                        Console.WriteLine("Feature exists but has a different error code.");
                    }
                }
                else
                {
                    Console.WriteLine("FeatureExtrusion3 returned NULL. Attempting to diagnose sketch issues...");
                    
                    // Retrieve the sketch
                    bool status = doc.Extension.SelectByID2("Sketch1", "SKETCH", 0, 0, 0, false, 0, null, 0);
                    if (status)
                    {
                        ISelectionMgr swSelMgr = (ISelectionMgr)doc.SelectionManager;
                        IFeature sketchFeat = (IFeature)swSelMgr.GetSelectedObject6(1, -1);
                        
                        if (sketchFeat != null)
                        {
                            ISketch sketch = (ISketch)sketchFeat.GetSpecificFeature2();
                            if (sketch != null)
                            {
                                int openCount = 0;
                                int closedCount = 0;
                                int checkStatus = sketch.CheckFeatureUse((int)swSketchCheckFeatureProfileUsage_e.swSketchCheckFeature_BASEEXTRUDE, ref openCount, ref closedCount);
                                
                                Console.WriteLine($"Sketch Check Status: {checkStatus}");
                                Console.WriteLine($"Open Contours: {openCount}");
                                Console.WriteLine($"Closed Contours: {closedCount}");

                                // Check for self-intersecting status
                                // swSketchCheckFeatureStatus_CturXCtur = 4
                                // swSketchCheckFeatureStatus_EntXSelf = 6
                                // swSketchCheckFeatureStatus_EntXEnt = 5
                                
                                if (checkStatus == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_CturXCtur ||
                                    checkStatus == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_EntXSelf ||
                                    checkStatus == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_EntXEnt)
                                {
                                     Console.WriteLine("SUCCESS: Detected self-intersecting geometry via CheckFeatureUse.");
                                     Console.WriteLine($"Specific Error Code: {(swSketchCheckFeatureStatus_e)checkStatus}");
                                }
                                else
                                {
                                     Console.WriteLine($"Sketch status is {(swSketchCheckFeatureStatus_e)checkStatus}, which might not be self-intersection.");
                                }
                            }
                            else
                            {
                                Console.WriteLine("Could not get ISketch interface.");
                            }
                        }
                        else
                        {
                            Console.WriteLine("Could not get sketch feature object.");
                        }
                    }
                    else
                    {
                        Console.WriteLine("Could not select Sketch1 for diagnosis.");
                    }
                }

            }
            catch (Exception ex)
            {
                Console.WriteLine("CRITICAL ERROR: " + ex.Message);
                Console.WriteLine(ex.StackTrace);
            }
        }
    }
}
