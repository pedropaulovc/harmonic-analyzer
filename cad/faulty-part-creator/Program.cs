using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System;
using System.Runtime.InteropServices;
using System.IO;
using System.Text.RegularExpressions;

namespace FaultyPartCreator
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
                    swApp = (SldWorks)Activator.CreateInstance(Type.GetTypeFromProgID("SldWorks.Application"));
                }
                
                if (swApp == null) throw new Exception("Failed to connect to SolidWorks.");
                swApp.Visible = true;

                swApp.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swImportAutoRunImportDiagnostics, false);
                
                Console.WriteLine("Creating valid cylinder...");
                ModelDoc2 doc = (ModelDoc2)swApp.NewDocument(swApp.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplatePart), 0, 0, 0);
                if (doc == null) doc = (ModelDoc2)swApp.NewDocument("", 0, 0, 0);

                // Create Cylinder R=0.01
                doc.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, false, 0, null, 0);
                doc.SketchManager.InsertSketch(true);
                doc.SketchManager.CreateCircle(0, 0, 0, 0.01, 0, 0);
                doc.SketchManager.InsertSketch(true);
                doc.FeatureManager.FeatureExtrusion3(true, false, false, 0, 0, 0.05, 0, false, false, false, false, 0, 0, false, false, false, false, true, true, true, 0, 0, false);

                string tempDir = System.IO.Path.GetTempPath();
                string validStep = System.IO.Path.Combine(tempDir, "valid_cyl.step");
                string faultyStep = System.IO.Path.Combine(tempDir, "faulty_cyl.step");

                int err = 0, warn = 0;
                doc.Extension.SaveAs(validStep, (int)swSaveAsVersion_e.swSaveAsCurrentVersion, (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref err, ref warn);
                swApp.CloseDoc(doc.GetTitle());

                Console.WriteLine("Corrupting STEP (Circle Radius)...");
                string content = File.ReadAllText(validStep);
                
                // Regex match CYLINDRICAL_SURFACE
                // CYLINDRICAL_SURFACE ( '', #Axis, Radius )
                Regex rx = new Regex(@"CYLINDRICAL_SURFACE\s*\([^\)]+,\s*([0-9\.\+\-E]+)\s*\)", RegexOptions.IgnoreCase);
                
                if (rx.IsMatch(content))
                {
                    content = rx.Replace(content, match => {
                        string original = match.Groups[1].Value;
                        return match.Value.Replace(original, "0.0001"); 
                    }, 1);
                    Console.WriteLine("Replaced CYLINDRICAL_SURFACE radius.");
                }
                else
                {
                    Console.WriteLine("Could not find CYLINDRICAL_SURFACE definition.");
                }

                File.WriteAllText(faultyStep, content);

                Console.WriteLine("Importing faulty STEP...");
                doc = (ModelDoc2)swApp.LoadFile4(faultyStep, "r", null, ref err);
                if (doc == null) throw new Exception("Failed to load faulty STEP.");

                PartDoc part = (PartDoc)doc;
                object[] bodies = (object[])part.GetBodies2((int)swBodyType_e.swSolidBody, false);
                if (bodies == null) throw new Exception("No bodies imported.");

                Console.WriteLine($"Imported {bodies.Length} bodies. Checking for faults...");
                bool faultFound = false;
                foreach (Body2 body in bodies)
                {
                    FaultEntity fault = body.Check3;
                    if (fault != null && fault.Count > 0)
                    {
                        faultFound = true;
                        Console.WriteLine($"Fault Count: {fault.Count}");
                        for(int i=0; i<fault.Count; i++)
                            Console.WriteLine($"Error Code: {(swFaultEntityErrorCode_e)fault.get_ErrorCode(i)}");
                    }
                }

                if (faultFound) Console.WriteLine("SUCCESS: Fault detected.");
                else throw new Exception("No faults detected.");
            }
            catch (Exception ex)
            {
                Console.WriteLine("ERROR: " + ex.Message);
                System.Environment.Exit(1);
            }
        }
    }
}
