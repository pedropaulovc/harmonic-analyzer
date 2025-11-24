using System;
using System.IO;
using System.Text.RegularExpressions;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace SolidWorksRenders
{
    public class FaultyGeometryTest : IPartCreator
    {
        private readonly ISldWorks _swApp;
        public string PartName => "Faulty Geometry Test";
        public string FileName => "faulty-geometry-test.SLDPRT";

        public FaultyGeometryTest(ISldWorks swApp)
        {
            _swApp = swApp ?? throw new ArgumentNullException(nameof(swApp));
        }

        public IModelDoc2 CreatePart()
        {
            // Disable import diagnostics
            _swApp.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swImportAutoRunImportDiagnostics, false);

            // Create valid cylinder
            IModelDoc2 doc = CreateCylinder();
            string validStep = ExportToStep(doc, "valid_cyl.step");
            _swApp.CloseDoc(doc.GetTitle());

            // Corrupt the STEP file - make radius impossibly small
            string faultyStep = CorruptCylinderRadius(validStep);

            // Import faulty STEP
            int errors = 0;
            doc = (IModelDoc2)_swApp.LoadFile4(faultyStep, "r", null, ref errors);
            if (doc == null) throw new Exception("Failed to load faulty STEP file.");

            // Verify fault exists
            VerifyFaultExists(doc);

            return doc;
        }

        private IModelDoc2 CreateCylinder()
        {
            IModelDoc2 doc = (IModelDoc2)_swApp.NewDocument(
                _swApp.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplatePart), 0, 0, 0);
            if (doc == null) doc = (IModelDoc2)_swApp.NewDocument("", 0, 0, 0);

            doc.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, false, 0, null, 0);
            doc.SketchManager.InsertSketch(true);
            doc.SketchManager.CreateCircle(0, 0, 0, 0.01, 0, 0);
            doc.SketchManager.InsertSketch(true);
            doc.FeatureManager.FeatureExtrusion3(true, false, false, 0, 0, 0.05, 0, false, false, false, false, 0, 0, false, false, false, false, true, true, true, 0, 0, false);

            return doc;
        }

        private string ExportToStep(IModelDoc2 doc, string filename)
        {
            string tempPath = Path.Combine(Path.GetTempPath(), filename);
            int errors = 0, warnings = 0;
            doc.Extension.SaveAs(tempPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
            return tempPath;
        }

        private string CorruptCylinderRadius(string validStepPath)
        {
            string content = File.ReadAllText(validStepPath);
            Regex rx = new Regex(@"CYLINDRICAL_SURFACE\s*\([^\)]+,\s*([0-9\.\+\-E]+)\s*\)", RegexOptions.IgnoreCase);

            content = rx.Replace(content, match => match.Value.Replace(match.Groups[1].Value, "0.0001"), 1);

            string faultyPath = validStepPath.Replace("valid_", "faulty_");
            File.WriteAllText(faultyPath, content);
            return faultyPath;
        }

        private void VerifyFaultExists(IModelDoc2 doc)
        {
            IPartDoc part = (IPartDoc)doc;
            object[] bodies = (object[])part.GetBodies2((int)swBodyType_e.swSolidBody, false);
            if (bodies == null) throw new Exception("No bodies imported.");

            bool faultFound = false;
            foreach (IBody2 body in bodies)
            {
                IFaultEntity fault = body.Check3;
                if (fault != null && fault.Count > 0)
                {
                    faultFound = true;
                    Console.WriteLine($"Fault Count: {fault.Count}");
                    for (int i = 0; i < fault.Count; i++)
                    {
                        swFaultEntityErrorCode_e errorCode = (swFaultEntityErrorCode_e)fault.get_ErrorCode(i);
                        Console.WriteLine($"Error {i + 1}: {errorCode}");
                    }
                }
            }

            if (!faultFound) throw new Exception("FAILURE: No faults detected in imported geometry!");
            Console.WriteLine("SUCCESS: Faulty geometry detected as expected.");
        }

        public void PrintPartDetails()
        {
            Console.WriteLine("This test verifies that corrupted STEP geometry produces detectable faults.");
        }
    }
}
