using System;
using System.IO;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using SolidWorksRenders;

namespace SolidWorksRenders
{
    class Program
    {
        static void Main(string[] args)
        {
            // TODO: In the future, this could be selected via command line args or config
            IPartCreator partCreator = CreatePartCreator(args);

            Console.WriteLine($"{partCreator.PartName} Creator for SolidWorks");
            Console.WriteLine(new string('=', partCreator.PartName.Length + 24) + "\n");

            ISldWorks? swApp = null;

            try
            {
                swApp = ConnectToSolidWorks();
                Console.WriteLine($"Connected to SolidWorks {swApp.RevisionNumber()}\n");

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

                    // Save the part
                    string savePath = SavePart(model, partCreator.FileName);
                    if (savePath != null)
                    {
                        Console.WriteLine($"\nPart saved to: {savePath}");
                    }

                    Console.WriteLine("\nThe part is now open in SolidWorks.");
                }
                else
                {
                    Console.Error.WriteLine($"ERROR: Failed to create {partCreator.PartName.ToLower()}.");
                }
            }
            catch (COMException comEx)
            {
                Console.Error.WriteLine($"COM ERROR: {comEx.Message}");
                Console.Error.WriteLine($"HRESULT: 0x{comEx.ErrorCode:X}");
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"ERROR: {ex.Message}");
                Console.Error.WriteLine($"Stack trace: {ex.StackTrace}");
            }

            Console.WriteLine("\nPress any key to exit...");
            Console.ReadKey();
        }

        /// <summary>
        /// Creates the appropriate part creator based on configuration
        /// Usage: SolidWorksRenders.exe [part-name]
        /// Available parts: harmonic-base, eccentric-cam, amplitude-bar, summing-lever, extrusion-test
        /// </summary>
        private static IPartCreator CreatePartCreator(string[] args)
        {
            ISldWorks swApp = ConnectToSolidWorks();

            // Check if a part name was provided as an argument
            string partName = args.Length > 0 ? args[0].ToLower() : "harmonic-base";

            switch (partName)
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

                default:
                    Console.WriteLine($"Unknown part name: {args[0]}");
                    Console.WriteLine("Available parts: harmonic-base, eccentric-cam, amplitude-bar, summing-lever, extrusion-test");
                    Console.WriteLine("Defaulting to harmonic-base\n");
                    return new HarmonicBase(swApp);
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
        /// Saves the part to the sldprt-renders directory
        /// </summary>
        /// <param name="model">The model to save</param>
        /// <param name="fileName">The filename to save as</param>
        /// <returns>The full path where the file was saved, or null if save failed</returns>
        private static string SavePart(IModelDoc2 model, string fileName)
        {
            try
            {
                // Get the directory relative to the current executable
                string exeDir = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
                string saveDir = Path.GetFullPath(Path.Combine(exeDir, "..", "..", "..", "..", "sldprt-renders"));

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
    }
}
