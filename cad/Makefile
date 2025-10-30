# Makefile for KCL CAD model export and rendering
# Generates STL files and Blender renders from KCL source files

# Tools
ZOO := zoo
BLENDER := "/c/Program Files/Blender Foundation/Blender 4.5/blender.exe"

# Files
KCL_FILE := console-bracket.kcl
STL_FILE := console-bracket.stl
RENDER_SCRIPT := render_bracket.py
RENDER_DIR := renders

# Render outputs
RENDERS := $(RENDER_DIR)/bracket_isometric.png \
           $(RENDER_DIR)/bracket_front.png \
           $(RENDER_DIR)/bracket_side.png \
           $(RENDER_DIR)/bracket_top.png \
           $(RENDER_DIR)/bracket_bottom.png \
           $(RENDER_DIR)/bracket_back.png

.PHONY: all clean renders stl

# Default target: generate STL and renders
all: $(RENDERS)

# Generate STL from KCL
stl: $(STL_FILE)

$(STL_FILE): $(KCL_FILE)
	@echo "Exporting KCL to STL..."
	$(ZOO) kcl export --output-format=stl $(KCL_FILE) .
	@if [ -f output.stl ]; then mv output.stl $(STL_FILE); fi
	@echo "Generated: $(STL_FILE)"

# Generate renders from STL
renders: $(RENDERS)

$(RENDERS): $(STL_FILE) $(RENDER_SCRIPT)
	@echo "Creating renders directory..."
	@mkdir -p $(RENDER_DIR)
	@echo "Rendering views with Blender..."
	$(BLENDER) --background --python $(RENDER_SCRIPT)
	@echo "Generated renders in $(RENDER_DIR)/"

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	rm -f $(STL_FILE)
	rm -rf $(RENDER_DIR)
	@echo "Clean complete"

# Help target
help:
	@echo "Available targets:"
	@echo "  all     - Generate STL and renders (default)"
	@echo "  stl     - Generate STL file from KCL"
	@echo "  renders - Generate Blender renders from STL"
	@echo "  clean   - Remove generated files"
	@echo "  help    - Show this help message"
