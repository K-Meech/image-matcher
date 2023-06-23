bl_info = {
    "name": "Image Matcher",
    "author": "Kimberly Meechan",
    "version": (1, 0),
    "blender": (3, 4, 1),
    "location": "3D View -> UI SIDE PANEL ",
    "description": "Matches 2D images to the 3D model (builds on RT Studio's Camera Pnpoint plugin)",
    "warning": "",
    "doc_url": "",
    "category": "Export",
}


import bpy
from .export import OBJECT_OT_export_matches;


class ImageMatchSettings(bpy.types.PropertyGroup):
    export_filepath: bpy.props.StringProperty(
        name="Export filepath",
        default="",
        description="Define the export filepath for image matches",
        subtype="FILE_PATH"
        )
    
    model: bpy.props.PointerProperty(
        name="3D model",
        description="3D model",
        type=bpy.types.Object
    ) 


class ImageExportPanel(bpy.types.Panel):
    """Creates a Panel in the scene context of the properties editor"""
    bl_label = "Image Match Export"
    bl_idname = "VIEW3D_PT_ImageExport"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Solve"
    # bl_space_type = 'PROPERTIES'
    # bl_region_type = 'WINDOW'
    # bl_context = "scene"

    def draw(self, context):
        layout = self.layout

        settings = context.scene.match_settings
        # scene = context.scene

        row = layout.row(align=True)
        row.label(text="3D model :")
        row.prop(settings, "model", text="")

        row = layout.row(align=True)
        row.label(text="Export filepath :")
        row.prop(settings, "export_filepath", text="")

        row = layout.row()
        row.operator("imagematches.export_matches")


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
