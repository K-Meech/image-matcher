import bpy
from bpy.types import Operator
from mathutils import Vector, Quaternion
import json
import math


def get_camera_position(camera_object, three_js=False):
    """Get position of camera

    Args:
        camera_object: Blender camera object
        three_js: Exports for three-js if true, otherwise for Blender.

    Returns:
        The camera location as [X, Y, Z]
    """

    camera_location = camera_object.location

    if three_js:
        # Account for Y-UP axis orientation
        return [camera_location.x, camera_location.z, -camera_location.y]
    else:
        return [camera_location.x, camera_location.y, camera_location.z]


def get_camera_quaternion(camera_object, three_js=False):
    """Get quaternion of camera

    Args:
        camera_object: Blender camera object
        three_js: Exports for three-js if true, otherwise for Blender.

    Returns:
        Quaternion as [W, X, Y, Z] for Blender, or [X, Y, Z, W] for three-js
    """

    camera_matrix = camera_object.matrix_world.copy()

    if three_js:
        # Convert to Y-UP - same way normal blender gltf exporter does
        correction = Quaternion((2**0.5 / 2, -(2**0.5) / 2, 0.0, 0.0))
        camera_matrix @= correction.to_matrix().to_4x4()
        corrected_quaternion = camera_matrix.to_quaternion()

        # Account for Y-UP axis orientation
        return [
            corrected_quaternion.x,
            corrected_quaternion.z,
            -corrected_quaternion.y,
            corrected_quaternion.w,
        ]
    else:
        quaternion = camera_matrix.to_quaternion()
        return [quaternion.w, quaternion.x, quaternion.y, quaternion.z]


def get_camera_lens(camera_object, three_js=False):
    """Get lens parameters of camera

    Args:
        camera_object: Blender camera object
        three_js: Exports for three-js if true, otherwise for Blender.

    Returns:
        Focal length for Blender, or field of view (fov) for three-js
    """

    camera_data = camera_object.data

    if three_js:
        render = bpy.context.scene.render
        width = render.pixel_aspect_x * render.resolution_x
        height = render.pixel_aspect_y * render.resolution_y
        aspect_ratio = width / height

        if width >= height:
            if camera_data.sensor_fit != "VERTICAL":
                camera_fov = 2.0 * math.atan(
                    math.tan(camera_data.angle * 0.5) / aspect_ratio
                )
            else:
                camera_fov = camera_data.angle
        else:
            if camera_data.sensor_fit != "HORIZONTAL":
                camera_fov = camera_data.angle
            else:
                camera_fov = 2.0 * math.atan(
                    math.tan(camera_data.angle * 0.5) / aspect_ratio
                )

        # Convert from radians to degrees
        return camera_fov * (180 / math.pi)
    else:
        return camera_data.lens


def calculate_camera_intersection(camera_object, model, three_js):
    """Calculate 3D point on model surface where central camera ray intersects.
    I.e. the point on the 3D model that aligns with the centre of the matched
    image

    Args:
        camera_object: Blender camera object
        model: Blender 3D model
        three_js: Exports for three-js if true, otherwise for Blender.

    Returns:
        3D point as [X, Y, Z]
    """

    # vector along direction camera points
    camera_direction = Vector((0, 0, -1))
    camera_direction.rotate(camera_object.rotation_euler)
    camera_direction.normalize()

    # get the position/direction relative to the model
    matrix = model.matrix_world.copy()
    matrix_inv = matrix.inverted()
    ray_origin = camera_object.location
    ray_target = ray_origin + camera_direction
    
    ray_origin_obj = matrix_inv @ ray_origin
    ray_target_obj = matrix_inv @ ray_target
    ray_direction_obj = ray_target_obj - ray_origin_obj

    # Get hit position
    cast_result = model.ray_cast(ray_origin_obj, ray_direction_obj)
    hit_position = matrix @ cast_result[1]

    if three_js:
        # Account for Y-UP axis orientation
        return [hit_position.x, hit_position.z, -hit_position.y]
    else:
        return [hit_position.x, hit_position.y, hit_position.z]


def convert_camera_settings(camera_object, model, three_js=False):
    """Get summary of camera settings. All ThreeJS export options are
    based on the official blender GLTF exporter plugin.

    Args:
        camera_object: Blender camera object
        model: Blender 3D model
        three_js: Exports for three-js if true, otherwise for Blender.

    Returns:
        Dictionary with the following keys -
        camera_fov - camera field of view (only for three-js)
        camera_focal_length - camera focal length (only for Blender)
        camera_quaternion - camera quaternion
        camera_position - camera position
        camera_near - camera clip start
        camera_far - camera clip end
        center_model_point - point on 3D model surface where central camera ray intersects
    """

    camera_data = camera_object.data
    match = {}

    lens = get_camera_lens(camera_object, three_js)
    if three_js:
        match["camera_fov"] = lens
    else:
        match["camera_focal_length"] = lens

    match["camera_quaternion"] = get_camera_quaternion(camera_object, three_js)
    match["camera_position"] = get_camera_position(camera_object, three_js)

    match["camera_near"] = camera_data.clip_start
    match["camera_far"] = camera_data.clip_end

    match["centre_model_point"] = calculate_camera_intersection(
        camera_object, model, three_js
    )

    return match


def export_to_json(matches, export_filepath):
    """Export image matches to JSON file"""

    output = {}
    output["image_matches"] = matches

    # Serializing json
    json_object = json.dumps(output, indent=4)

    # Writing to sample.json
    json_filepath = bpy.path.abspath(export_filepath)
    if not json_filepath.endswith(".json"):
        json_filepath += ".json"

    with open(json_filepath, "w") as outfile:
        outfile.write(json_object)


class OBJECT_OT_export_matches(Operator):
    """Exports all image match settings to the specified JSON file with either
    Blender or ThreeJS settings"""

    bl_idname = "imagematches.export_matches"
    bl_label = "Export matches"

    def execute(self, context):
        settings = context.scene.match_settings

        if settings.model is None:
            self.report({"ERROR"}, "No 3D model selected")
            return {"CANCELLED"}

        if settings.export_filepath == "":
            self.report({"ERROR"}, "No export filepath selected")
            return {"CANCELLED"}

        if settings.export_type == "THREEJS":
            three_js = True
        else:
            three_js = False

        matches = []

        for image_match in settings.image_matches:
            camera = image_match.camera

            match = convert_camera_settings(camera, settings.model, three_js)
            match["image_filename"] = image_match.full_name
            matches.append(match)

        export_to_json(matches, settings.export_filepath)

        return {"FINISHED"}
