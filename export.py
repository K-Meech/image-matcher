import bpy
from bpy.types import Operator
from mathutils import Vector, Quaternion
import json
import math
import os


def convert_camera_settings(camera_name):
    camera_data = bpy.data.cameras[camera_name]
    camera_object = bpy.data.objects[camera_name]

    image_point = {}

    # Based on the official blender GLTF exporter plugin
    render = bpy.context.scene.render
    width = render.pixel_aspect_x * render.resolution_x
    height = render.pixel_aspect_y * render.resolution_y
    aspect_ratio = width / height

    if width >= height:
        if camera_data.sensor_fit != 'VERTICAL':
            camera_fov = 2.0 * math.atan(
                math.tan(camera_data.angle * 0.5) / aspect_ratio)
        else:
            camera_fov = camera_data.angle
    else:
        if camera_data.sensor_fit != 'HORIZONTAL':
            camera_fov = camera_data.angle
        else:
            camera_fov = 2.0 * math.atan(
                math.tan(camera_data.angle * 0.5) / aspect_ratio)
    
    # Convert from radians to degrees
    image_point["camera_fov"] = camera_fov * (180/math.pi)

    image_point["camera_near"] = camera_data.clip_start
    image_point["camera_far"] = camera_data.clip_end

    # Get name of corresponding image (always with jpg extension)
    image_file = camera_data.background_images[0].clip.filepath
    image_file = os.path.basename(image_file)
    image_file = os.path.splitext(image_file)[0]+'.jpg'
    image_point["image_filename"] = image_file

    # Convert to Y-UP - same way normal blender gltf exporter does
    camera_matrix = camera_object.matrix_world.copy()
    correction = Quaternion((2**0.5/2, -2**0.5/2, 0.0, 0.0))
    camera_matrix @= correction.to_matrix().to_4x4()
    corrected_quaternion = camera_matrix.to_quaternion()

    # Account for Y-UP axis orientation
    image_point["camera_quaternion"] = [
        corrected_quaternion.x,
        corrected_quaternion.z,
        -corrected_quaternion.y,
        corrected_quaternion.w
    ]

    corrected_location = camera_object.location
    # Account for Y-UP axis orientation
    image_point["camera_position"] = [
        corrected_location.x, corrected_location.z, -corrected_location.y]
    
    return image_point


def calculate_camera_intersection(camera_name):
    """Calculate intersection point of camera ray and 3D model"""
    model = bpy.context.scene.match_settings.model
    camera_object = bpy.data.objects[camera_name]

    # vector along direction camera points
    camera_direction = Vector((0, 0, -1))
    camera_direction.rotate(camera_object.rotation_euler)
    camera_direction.normalize()
    
    # Needs any rotation/scaling etc of model to be applied!!
    # If not I would need to convert the camera location / direction to the 
    # mesh's local space for this to work properly
    cast_result = model.ray_cast(camera_object.location, camera_direction)
    # cast_result = model.ray_cast(Vector((0, 0, 100)), Vector((0, 0, -1)))

    hit_position = cast_result[1]
    # Account for Y-UP axis orientation
    hit_position_corrected = [
        hit_position.x, hit_position.z, -hit_position.y]

    return hit_position_corrected


def export_to_json(image_points):
    output = {}
    output["image_points"] = image_points

    # Serializing json
    json_object = json.dumps(output, indent=4)
 
    # Writing to sample.json
    json_filepath = bpy.path.abspath(
        bpy.context.scene.match_settings.export_filepath)
    if not json_filepath.endswith(".json"):
        json_filepath += ".json"

    with open(json_filepath, "w") as outfile:
        outfile.write(json_object)


class OBJECT_OT_export_matches(Operator):
    """Create a new Mesh Object"""
    bl_idname = "imagematches.export_matches"
    bl_label = "Export matches"
    # bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        image_points = []

        for camera_name in bpy.data.cameras.keys():
            image_point = convert_camera_settings(camera_name)
            image_point["point_position"] = \
                calculate_camera_intersection(camera_name)
            image_points.append(image_point)

        export_to_json(image_points)

        return {'FINISHED'}
