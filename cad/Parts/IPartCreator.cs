using SolidWorks.Interop.sldworks;

namespace SolidWorksRenders
{
    /// <summary>
    /// Interface for creating SolidWorks parts
    /// </summary>
    public interface IPartCreator
    {
        /// <summary>
        /// Gets the name of the part being created
        /// </summary>
        string PartName { get; }

        /// <summary>
        /// Gets the filename to save the part as (e.g., "eccentric-cam.sldprt")
        /// </summary>
        string FileName { get; }

        /// <summary>
        /// Gets a short description of the part for CLI help
        /// </summary>
        string Description { get; }

        /// <summary>
        /// Creates the part and returns the model document
        /// </summary>
        IModelDoc2 CreatePart();

        /// <summary>
        /// Prints part-specific details to the console
        /// </summary>
        void PrintPartDetails();
    }
}
