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

# Get the imported object
obj = bpy.context.selected_objects[0]
bpy.context.view_layer.objects.active = obj

# Center object at origin
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
obj.location = (0, 0, 0)

# Add material with metallic appearance
mat = bpy.data.materials.new(name="BracketMaterial")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1.0)
bsdf.inputs['Metallic'].default_value = 0.8
bsdf.inputs['Roughness'].default_value = 0.3
obj.data.materials.append(mat)

# Set up render settings - use EEVEE for fast rendering
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.eevee.taa_render_samples = 16
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'

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

# Add lighting - bright three point lighting setup
light_data = bpy.data.lights.new(name="KeyLight", type='AREA')
light_data.energy = 1000
light_data.size = 5
key_light = bpy.data.objects.new(name="KeyLight", object_data=light_data)
scene.collection.objects.link(key_light)
key_light.location = (5, -5, 10)
key_light.rotation_euler = (math.radians(45), 0, math.radians(45))

fill_light_data = bpy.data.lights.new(name="FillLight", type='AREA')
fill_light_data.energy = 500
fill_light_data.size = 5
fill_light = bpy.data.objects.new(name="FillLight", object_data=fill_light_data)
scene.collection.objects.link(fill_light)
fill_light.location = (-5, -3, 8)
fill_light.rotation_euler = (math.radians(45), 0, math.radians(-45))

back_light_data = bpy.data.lights.new(name="BackLight", type='AREA')
back_light_data.energy = 600
back_light_data.size = 5
back_light = bpy.data.objects.new(name="BackLight", object_data=back_light_data)
scene.collection.objects.link(back_light)
back_light.location = (0, 5, 8)
back_light.rotation_euler = (math.radians(135), 0, 0)

# Add camera
camera_data = bpy.data.cameras.new(name="Camera")
camera = bpy.data.objects.new("Camera", camera_data)
scene.collection.objects.link(camera)
scene.camera = camera

# Calculate object bounds for camera positioning
bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
max_dim = max(
    max(v.x for v in bbox) - min(v.x for v in bbox),
    max(v.y for v in bbox) - min(v.y for v in bbox),
    max(v.z for v in bbox) - min(v.z for v in bbox)
)

# Define camera views - zoomed out to show full bracket
views = {
    'isometric': {
        'location': (max_dim * 2.5, -max_dim * 2.5, max_dim * 2.0),
        'rotation': (math.radians(60), 0, math.radians(45))
    },
    'front': {
        'location': (0, -max_dim * 3, 0),
        'rotation': (math.radians(90), 0, 0)
    },
    'side': {
        'location': (max_dim * 3, 0, 0),
        'rotation': (math.radians(90), 0, math.radians(90))
    },
    'top': {
        'location': (0, 0, max_dim * 3),
        'rotation': (0, 0, 0)
    },
    'bottom': {
        'location': (0, 0, -max_dim * 3),
        'rotation': (math.radians(180), 0, 0)
    },
    'back': {
        'location': (0, max_dim * 3, 0),
        'rotation': (math.radians(90), 0, math.radians(180))
    }
}

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
