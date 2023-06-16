bl_info = {
    "name": "Image Matcher",
    "author": "Kimberly Meechan",
    "version": (1, 0),
    "blender": (3, 4, 1),
    "location": "3D View -> UI SIDE PANEL ",
    "description": "Matches 2D images to the 3D model",
    "warning": "",
    "doc_url": "",
    "category": "Export",
}


import bpy
from bpy.types import Operator
from bpy_extras.object_utils import AddObjectHelper, object_data_add
from mathutils import Vector, Quaternion, Matrix
import json
import math
import os


class ImageMatchSettings(bpy.types.PropertyGroup):
    export_filepath: bpy.props.StringProperty(
        name="Export filepath",
        default="",
        description="Define the export filepath for image matches",
        subtype="FILE_PATH"
        )


class ImageExportPanel(bpy.types.Panel):
    """Creates a Panel in the scene context of the properties editor"""
    bl_label = "Image Match Export"
    bl_idname = "SCENE_PT_ImageExport"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Image Match"
    # bl_space_type = 'PROPERTIES'
    # bl_region_type = 'WINDOW'
    # bl_context = "scene"

    def draw(self, context):
        layout = self.layout

        settings = context.scene.match_settings
        # scene = context.scene

        row = layout.row(align=True)
        row.label(text="Export filepath :")
        row.prop(settings, "export_filepath", text="")

        row = layout.row()
        row.operator("imagematches.export_matches")


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
            image_points.append(convert_camera_settings(camera_name))

        export_to_json(image_points)

        return {'FINISHED'}


# Registration
classes = [OBJECT_OT_export_matches,
           ImageExportPanel,
           ImageMatchSettings]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.match_settings = bpy.props.PointerProperty(
        type=ImageMatchSettings)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.match_settings


if __name__ == "__main__":
    register()
