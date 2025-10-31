import bpy
import math
import os
import mathutils
from pathlib import Path

# Clear existing scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Get the current directory
script_dir = Path(__file__).parent
stl_path = script_dir / "console-bracket.stl"
output_dir = script_dir / "renders"
output_dir.mkdir(exist_ok=True)

# Import STL
bpy.ops.wm.stl_import(filepath=str(stl_path))

# Get all imported objects (might be multiple)
imported_objs = list(bpy.context.selected_objects)
print(f"Imported {len(imported_objs)} object(s)")

# If multiple objects, join them into one
if len(imported_objs) > 1:
    bpy.context.view_layer.objects.active = imported_objs[0]
    for obj in imported_objs:
        obj.select_set(True)
    bpy.ops.object.join()

obj = bpy.context.active_object
print(f"Working with object: {obj.name}")

# Center object at origin
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
obj.location = (0, 0, 0)

# Print object dimensions for debugging
dims = obj.dimensions
print(f"Object dimensions: {dims.x:.2f} x {dims.y:.2f} x {dims.z:.2f}")

# Add material with metallic appearance - dark charcoal for contrast
mat = bpy.data.materials.new(name="BracketMaterial")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs['Base Color'].default_value = (0.15, 0.15, 0.18, 1.0)  # Dark charcoal with slight blue tint
bsdf.inputs['Metallic'].default_value = 0.9
bsdf.inputs['Roughness'].default_value = 0.2

# Clear any existing materials and add ours
obj.data.materials.clear()
obj.data.materials.append(mat)

# Ensure object is visible and has proper settings
obj.hide_render = False
obj.hide_viewport = False
obj.hide_set(False)

print(f"Material '{mat.name}' applied to {obj.name}")
print(f"Object has {len(obj.data.materials)} material(s)")
print(f"Object has {len(obj.data.polygons)} polygons")

# Make sure object is in the scene
scene = bpy.context.scene
if obj.name not in scene.collection.objects:
    scene.collection.objects.link(obj)
    print(f"Linked {obj.name} to scene collection")

# Update scene
bpy.context.view_layer.update()

# Set up render settings - use Cycles for reliable rendering
scene.render.engine = 'CYCLES'
scene.cycles.samples = 32  # Low samples for speed
scene.cycles.use_denoising = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'

print(f"Render engine: {scene.render.engine}")

# Set neon pink background
scene.render.film_transparent = False
if scene.world is None:
    scene.world = bpy.data.worlds.new("World")
scene.world.use_nodes = True
world_nodes = scene.world.node_tree.nodes
world_nodes.clear()
bg_node = world_nodes.new('ShaderNodeBackground')
bg_node.inputs['Color'].default_value = (1.0, 0.078, 0.576, 1.0)  # Neon pink
bg_node.inputs['Strength'].default_value = 1.0
output_node = world_nodes.new('ShaderNodeOutputWorld')
scene.world.node_tree.links.new(bg_node.outputs['Background'], output_node.inputs['Surface'])

# Calculate object dimensions for camera and lighting
max_dim = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z)
print(f"Max dimension: {max_dim:.2f}")

# Calculate lighting distance based on object size
light_dist = max_dim * 3
light_size = max_dim * 0.5

# Add lighting - bright three point lighting setup
light_data = bpy.data.lights.new(name="KeyLight", type='AREA')
light_data.energy = 1000
light_data.size = light_size
key_light = bpy.data.objects.new(name="KeyLight", object_data=light_data)
scene.collection.objects.link(key_light)
key_light.location = (light_dist * 0.5, -light_dist * 0.5, light_dist)
key_light.rotation_euler = (math.radians(45), 0, math.radians(45))

fill_light_data = bpy.data.lights.new(name="FillLight", type='AREA')
fill_light_data.energy = 500
fill_light_data.size = light_size
fill_light = bpy.data.objects.new(name="FillLight", object_data=fill_light_data)
scene.collection.objects.link(fill_light)
fill_light.location = (-light_dist * 0.5, -light_dist * 0.3, light_dist * 0.8)
fill_light.rotation_euler = (math.radians(45), 0, math.radians(-45))

back_light_data = bpy.data.lights.new(name="BackLight", type='AREA')
back_light_data.energy = 600
back_light_data.size = light_size
back_light = bpy.data.objects.new(name="BackLight", object_data=back_light_data)
scene.collection.objects.link(back_light)
back_light.location = (0, light_dist * 0.5, light_dist * 0.8)
back_light.rotation_euler = (math.radians(135), 0, 0)

print(f"Light distance: {light_dist:.2f}, size: {light_size:.2f}")

# Add camera
camera_data = bpy.data.cameras.new(name="Camera")
camera_data.lens = 50  # Standard lens
camera = bpy.data.objects.new("Camera", camera_data)
scene.collection.objects.link(camera)
scene.camera = camera

# Use larger multiplier for better framing
cam_distance = max_dim * 2.5

# Define camera views with better positioning
views = {
    'isometric': {
        'location': (cam_distance, -cam_distance, cam_distance * 0.8),
        'rotation': (math.radians(60), 0, math.radians(45))
    },
    'front': {
        'location': (0, -cam_distance, 0),
        'rotation': (math.radians(90), 0, 0)
    },
    'side': {
        'location': (cam_distance, 0, 0),
        'rotation': (math.radians(90), 0, math.radians(90))
    },
    'top': {
        'location': (0, 0, cam_distance),
        'rotation': (0, 0, 0)
    },
    'bottom': {
        'location': (0, 0, -cam_distance),
        'rotation': (math.radians(180), 0, 0)
    },
    'back': {
        'location': (0, cam_distance, 0),
        'rotation': (math.radians(90), 0, math.radians(180))
    }
}

print(f"Camera distance: {cam_distance:.2f}")

# Render each view
for view_name, view_config in views.items():
    camera.location = view_config['location']
    camera.rotation_euler = view_config['rotation']

    # Point camera at origin
    direction = mathutils.Vector((0, 0, 0)) - mathutils.Vector(camera.location)
    rot_quat = direction.to_track_quat('-Z', 'Y')
    camera.rotation_euler = rot_quat.to_euler()

    # Render
    output_path = output_dir / f"bracket_{view_name}.png"
    scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {view_name} view to {output_path}")

print("All renders complete!")
