using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using SolidWorksRenders;

namespace SolidWorksRenders
{
    class Program
    {
        static int Main(string[] args)
        {
            // Parse command-line arguments
            var options = CliOptions.Parse(args);

            // Handle parse errors
            if (!string.IsNullOrEmpty(options.Error))
            {
                Console.Error.WriteLine($"Error: {options.Error}");
                Console.WriteLine();
                CliOptions.PrintHelp();
                return 1;
            }

            // Handle help request
            if (options.ShowHelp)
            {
                CliOptions.PrintHelp();
                return 0;
            }

            // Handle list request
            if (options.ListComponents)
            {
                CliOptions.PrintComponentList();
                return 0;
            }

            // Get components to build
            var componentsToBuild = new List<string>(options.GetComponentsToBuild());
            if (componentsToBuild.Count == 0)
            {
                CliOptions.PrintHelp();
                return 1;
            }

            ISldWorks? swApp = null;
            int successCount = 0;
            int failCount = 0;

            try
            {
                swApp = ConnectToSolidWorks();
                Console.WriteLine($"Connected to SolidWorks {swApp.RevisionNumber()}\n");

                // Close all open documents first to avoid file lock issues
                CloseAllDocuments(swApp);

                // Build each component
                foreach (string componentName in componentsToBuild)
                {
                    Console.WriteLine(new string('=', 60));
                    bool success = BuildComponent(swApp, componentName);
                    if (success)
                        successCount++;
                    else
                        failCount++;
                    Console.WriteLine();
                }

                // Print summary if building multiple
                if (componentsToBuild.Count > 1)
                {
                    Console.WriteLine(new string('=', 60));
                    Console.WriteLine("BUILD SUMMARY");
                    Console.WriteLine(new string('=', 60));
                    Console.WriteLine($"  Successful: {successCount}");
                    Console.WriteLine($"  Failed:     {failCount}");
                    Console.WriteLine($"  Total:      {componentsToBuild.Count}");
                }
            }
            catch (COMException comEx)
            {
                Console.Error.WriteLine($"COM ERROR: {comEx.Message}");
                Console.Error.WriteLine($"HRESULT: 0x{comEx.ErrorCode:X}");
                return 1;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"ERROR: {ex.Message}");
                Console.Error.WriteLine($"Stack trace: {ex.StackTrace}");
                return 1;
            }

            // Only prompt for key if running interactively
            if (!Console.IsInputRedirected)
            {
                Console.WriteLine("\nPress any key to exit...");
                Console.ReadKey();
            }

            return failCount > 0 ? 1 : 0;
        }

        /// <summary>
        /// Build a single component by name
        /// </summary>
        private static bool BuildComponent(ISldWorks swApp, string componentName)
        {
            IPartCreator? partCreator = CreatePartCreator(swApp, componentName);
            if (partCreator == null)
            {
                Console.Error.WriteLine($"ERROR: Unknown component '{componentName}'");
                return false;
            }

            Console.WriteLine($"Building: {partCreator.PartName}");
            Console.WriteLine(new string('-', 60));

            try
            {
                // Create the part
                Console.WriteLine($"Creating {partCreator.PartName.ToLower()} part...");
                IModelDoc2 model = partCreator.CreatePart();

                if (model != null)
                {
                    Console.WriteLine($"SUCCESS: {partCreator.PartName} created successfully!");
                    Console.WriteLine($"Model name: {model.GetTitle()}");

                    // Zoom to fit
                    model.ViewZoomtofit2();

                    // Print part-specific details
                    partCreator.PrintPartDetails();

                    // Save the part as SLDPRT
                    string? savePath = SavePart(model, partCreator.FileName);
                    if (savePath != null)
                    {
                        Console.WriteLine($"Part saved to: {savePath}");
                    }

                    // Export to STL
                    string? stlPath = ExportToSTL(model, partCreator.FileName);
                    if (stlPath != null)
                    {
                        Console.WriteLine($"STL exported to: {stlPath}");
                    }

                    // Export to STEP
                    string? stepPath = ExportToSTEP(model, partCreator.FileName);
                    if (stepPath != null)
                    {
                        Console.WriteLine($"STEP exported to: {stepPath}");
                    }

                    // Keep document open for inspection
                    Console.WriteLine("Part remains open in SolidWorks for inspection.");

                    return true;
                }
                else
                {
                    Console.Error.WriteLine($"ERROR: Failed to create {partCreator.PartName.ToLower()}.");
                    return false;
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"ERROR building {componentName}: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Creates the appropriate part creator based on component name
        /// </summary>
        private static IPartCreator? CreatePartCreator(ISldWorks swApp, string componentName)
        {
            switch (componentName.ToLower())
            {
                case "harmonic-base":
                    return new HarmonicBase(swApp);

                case "eccentric-cam":
                    return new EccentricCam(swApp);

                case "amplitude-bar":
                    return new AmplitudeBar(swApp);

                case "summing-lever":
                    return new SummingLever(swApp);

                case "extrusion-test":
                    return new ExtrusionTroubleshootingTest(swApp);

                case "rocker-arm-support":
                    return new RockerArmSupport(swApp);

                default:
                    return null;
            }
        }

        /// <summary>
        /// Close all open documents in SolidWorks to release file locks
        /// </summary>
        private static void CloseAllDocuments(ISldWorks swApp)
        {
            try
            {
                // Get the first document
                IModelDoc2 doc = (IModelDoc2)swApp.GetFirstDocument();
                int closedCount = 0;

                while (doc != null)
                {
                    string docTitle = doc.GetTitle();
                    IModelDoc2 nextDoc = (IModelDoc2)doc.GetNext();

                    // Close without saving (we'll rebuild fresh)
                    swApp.CloseDoc(docTitle);
                    closedCount++;

                    doc = nextDoc;
                }

                if (closedCount > 0)
                {
                    Console.WriteLine($"Closed {closedCount} existing document(s) to avoid file locks.\n");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Warning: Could not close all documents: {ex.Message}");
            }
        }

        /// <summary>
        /// Connects to a running SolidWorks instance or creates a new one
        /// </summary>
        private static ISldWorks ConnectToSolidWorks()
        {
            Console.WriteLine("Connecting to SolidWorks...");

            try
            {
                ISldWorks? swApp = (ISldWorks?)Marshal.GetActiveObject("SldWorks.Application");
                if (swApp != null)
                {
                    return swApp;
                }
            }
            catch (COMException)
            {
                // No running instance found, will create new one below
            }

            Console.WriteLine("No running SolidWorks instance found. Starting SolidWorks...");

            // Create a new instance of SolidWorks
            Type? swType = Type.GetTypeFromProgID("SldWorks.Application");
            if (swType == null)
            {
                throw new InvalidOperationException("SolidWorks is not installed or not properly registered.");
            }

            ISldWorks? newSwApp = (ISldWorks?)Activator.CreateInstance(swType);
            if (newSwApp == null)
            {
                throw new InvalidOperationException("Failed to create SolidWorks instance.");
            }

            // Make SolidWorks visible
            newSwApp.Visible = true;

            return newSwApp;
        }

        /// <summary>
        /// Saves the part to the out/sldprt directory
        /// </summary>
        /// <param name="model">The model to save</param>
        /// <param name="fileName">The filename to save as</param>
        /// <returns>The full path where the file was saved, or null if save failed</returns>
        private static string? SavePart(IModelDoc2 model, string fileName)
        {
            try
            {
                // Get the directory relative to the current executable
                string exeDir = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
                string saveDir = Path.GetFullPath(Path.Combine(exeDir, "..", "..", "..", "..", "out", "sldprt"));

                // Create directory if it doesn't exist
                if (!Directory.Exists(saveDir))
                {
                    Directory.CreateDirectory(saveDir);
                    Console.WriteLine($"Created directory: {saveDir}");
                }

                // Construct full save path
                string fullPath = Path.Combine(saveDir, fileName);

                Console.WriteLine($"Saving part to: {fullPath}");

                // Save the document using IModelDocExtension.SaveAs3
                int errors = 0;
                int warnings = 0;
                bool saveResult = model.Extension.SaveAs3(
                    Name: fullPath,
                    Version: (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    Options: (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
                    ExportData: null,
                    AdvancedSaveAsOptions: null,
                    Errors: ref errors,
                    Warnings: ref warnings);

                if (!saveResult || errors != 0)
                {
                    Console.Error.WriteLine($"ERROR: Failed to save part. Errors: {errors}, Warnings: {warnings}");
                    return null;
                }

                return fullPath;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"ERROR saving part: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Exports the part to STL format in the out/stl directory
        /// </summary>
        /// <param name="model">The model to export</param>
        /// <param name="fileName">The filename (without extension) to export as</param>
        /// <returns>The full path where the file was exported, or null if export failed</returns>
        private static string? ExportToSTL(IModelDoc2 model, string fileName)
        {
            try
            {
                // Get the directory relative to the current executable
                string exeDir = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
                string saveDir = Path.GetFullPath(Path.Combine(exeDir, "..", "..", "..", "..", "out", "stl"));

                // Create directory if it doesn't exist
                if (!Directory.Exists(saveDir))
                {
                    Directory.CreateDirectory(saveDir);
                    Console.WriteLine($"Created directory: {saveDir}");
                }

                // Replace .sldprt extension with .stl
                string stlFileName = Path.GetFileNameWithoutExtension(fileName) + ".stl";
                string fullPath = Path.Combine(saveDir, stlFileName);

                Console.WriteLine($"Exporting to STL: {fullPath}");

                // Clear selection to export entire model
                model.ClearSelection2(true);

                // Export using SaveAs3 - the .stl extension triggers STL format
                int errors = 0;
                int warnings = 0;
                bool saveResult = model.Extension.SaveAs3(
                    Name: fullPath,
                    Version: (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    Options: (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
                    ExportData: null,
                    AdvancedSaveAsOptions: null,
                    Errors: ref errors,
                    Warnings: ref warnings);

                if (!saveResult || errors != 0)
                {
                    Console.Error.WriteLine($"ERROR: Failed to export STL. Errors: {errors}, Warnings: {warnings}");
                    return null;
                }

                return fullPath;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"ERROR exporting to STL: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Exports the part to STEP format in the out/step directory
        /// </summary>
        /// <param name="model">The model to export</param>
        /// <param name="fileName">The filename (without extension) to export as</param>
        /// <returns>The full path where the file was exported, or null if export failed</returns>
        private static string? ExportToSTEP(IModelDoc2 model, string fileName)
        {
            try
            {
                // Get the directory relative to the current executable
                string exeDir = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
                string saveDir = Path.GetFullPath(Path.Combine(exeDir, "..", "..", "..", "..", "out", "step"));

                // Create directory if it doesn't exist
                if (!Directory.Exists(saveDir))
                {
                    Directory.CreateDirectory(saveDir);
                    Console.WriteLine($"Created directory: {saveDir}");
                }

                // Replace .sldprt extension with .step
                string stepFileName = Path.GetFileNameWithoutExtension(fileName) + ".step";
                string fullPath = Path.Combine(saveDir, stepFileName);

                Console.WriteLine($"Exporting to STEP: {fullPath}");

                // Clear selection to export entire model
                model.ClearSelection2(true);

                // Export using SaveAs3 - the .step extension triggers STEP format
                int errors = 0;
                int warnings = 0;
                bool saveResult = model.Extension.SaveAs3(
                    Name: fullPath,
                    Version: (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    Options: (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
                    ExportData: null,
                    AdvancedSaveAsOptions: null,
                    Errors: ref errors,
                    Warnings: ref warnings);

                if (!saveResult || errors != 0)
                {
                    Console.Error.WriteLine($"ERROR: Failed to export STEP. Errors: {errors}, Warnings: {warnings}");
                    return null;
                }

                return fullPath;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"ERROR exporting to STEP: {ex.Message}");
                return null;
            }
        }
    }
}
