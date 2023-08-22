bl_info = {
    "name": "Image Matcher",
    "author": "Kimberly Meechan",
    "version": (1, 0),
    "blender": (3, 4, 1),
    "location": "Clip Editor > Tools > Solve > Image Matcher",
    "description": "Matches 2D images to the 3D model (builds on RT Studio's Camera Pnpoint plugin)",
    "warning": "",
    "doc_url": "",
    "category": "Export",
}


import bpy
import subprocess
from collections import namedtuple
from .export import OBJECT_OT_export_matches
from . import dependency
from .image import IMAGE_OT_add_image, IMAGE_OT_swap_image, \
    IMAGE_OT_point_mode, IMAGE_OT_add_3d_point, IMAGE_OT_add_2d_point, \
        IMAGE_OT_delete_3d_point, IMAGE_OT_delete_2d_point, set_point_mode


def poll_image_collection(self, object):
    """Only allow selection of collections inside the result collection"""
    result_collection = bpy.data.collections[self.image_match_collection]
    return object.name in result_collection.children


def update_active_point_match(self, context):
    active_point_index = self.active_point_index
    active_point_match = self.current_points[active_point_index]

    # Select the current 3d point
    bpy.ops.object.select_all(action='DESELECT')
    if active_point_match.is_point_3d_initialised:
        active_point_match.point_3d.select_set(True)
        bpy.context.view_layer.objects.active = active_point_match.point_3d

    # Select the current 2d point
    bpy.ops.clip.select_all(action='DESELECT')
    if active_point_match.is_point_2d_initialised:
        track_name = active_point_match.point_2d
        current_movie_clip = context.edit_movieclip  
        tracks = current_movie_clip.tracking.objects[0].tracks
        for track in tracks:
            if track.name == track_name:
                track.select = True
                tracks.active = track
                break


def force_redraw(self, context):
    """This empty update function makes Blender re-draw the panel, which 
    ensures that as 3D points are added, they immediately show up in the 
    UI list"""
    pass
            

class PointMatch(bpy.types.PropertyGroup):
    """Group of properties representing a 2D-3D point match"""

    # id: bpy.props.IntProperty(
    #        name="Point id",
    #        description="Id of this point match",
    #        default=1)

    is_point_2d_initialised: bpy.props.BoolProperty(
        name="2D point",
        description="Is 2D point initialised?",
        default=False)
    
    is_point_3d_initialised: bpy.props.BoolProperty(
        name="3D point",
        description="Is 3D point initialised?",
        default=False,
        update=force_redraw)
    
    point_3d: bpy.props.PointerProperty(
        name="3D point",
        type=bpy.types.Object)
    
    # Name of track for this 2D point. Don't seem to be
    # able to directly store a pointer to the track
    point_2d: bpy.props.StringProperty(
        name="Name of point 2D track",
        default="",
        description="Name of track for this 2D point")
    
    point_3d: bpy.props.PointerProperty(
        name="3D point",
        type=bpy.types.Object)


class ImageMatchSettings(bpy.types.PropertyGroup):

    export_filepath: bpy.props.StringProperty(
        name="Export filepath",
        default="",
        description="Define the export filepath for image matches",
        subtype="FILE_PATH")
    
    model: bpy.props.PointerProperty(
        name="3D model",
        description="3D model",
        type=bpy.types.Object)

    points_3d_collection: bpy.props.PointerProperty(
        name="",
        type=bpy.types.Collection)
    
    points_3d_collection_name: bpy.props.StringProperty(
        name="3D points Collection",
        description="Collection for 3D points",
        default="points-3d")
    
    pnp_intrinsics_focal_length: bpy.props.BoolProperty(
        name="Focal Length",
        description="Calibrate Focal Length",
        default=True)
    
    pnp_intrinsics_principal_point: bpy.props.BoolProperty(
        name="Optical Center",
        description="Calibrate Optical Center",
        default=False)
    
    pnp_intrinsics_distortion_k1: bpy.props.BoolProperty(
        name="Distortion K1",
        description="Calibrate Radial Distortion K1",
        default=False)
    
    pnp_intrinsics_distortion_k2: bpy.props.BoolProperty(
        name="Distortion K2",
        description="Calibrate Radial Distortion K2",
        default=False)
    
    pnp_intrinsics_distortion_k3: bpy.props.BoolProperty(
        name="Distortion K3",
        description="Calibrate Radial Distortion K3",
        default=False)
    
    pnp_msg: bpy.props.StringProperty(
        name="Information",
        description="Solver Output Message",
        default="")
    
    image_filepath: bpy.props.StringProperty(
        name="Image filepath",
        default="",
        description="Define the import filepath for image",
        subtype="FILE_PATH")
    
    image_match_collection: bpy.props.StringProperty(
        name="Image Match Collection",
        description="Collection for image match results",
        default="image-match")
    
    current_image_collection: bpy.props.PointerProperty(
        name="",
        type=bpy.types.Collection,
        poll=poll_image_collection)
    
    point_mode_enabled: bpy.props.BoolProperty(
        name="Point mode enabled",
        description="Point mode enabled",
        default=False,
        update=set_point_mode
    )

    active_point_index: bpy.props.IntProperty(
        name = "Active point index",
        description = "Active point index",
        default = 0,
        update = update_active_point_match
    )

    current_points: bpy.props.CollectionProperty(
        type = PointMatch,
        name = "Current points",
        description ="Current points")
    

class POINT_UL_UI(bpy.types.UIList):
    """UI for point list"""

    def draw_item(self, context, layout, data, point, icon, active_data,
                  active_propname, index):
        icon = "EMPTY_DATA"

        row = layout.row()

        col = layout.column()
        col.label(text="", icon=icon)

        col = layout.column()
        col.enabled = False
        col.prop(point, "is_point_2d_initialised", text="2D")
        
        col = layout.column()
        col.enabled = False
        col.prop(point, "is_point_3d_initialised", text="3D")

        col = layout.column()
        if point.is_point_2d_initialised:
            col.enabled = True
        else:
            col.enabled = False
        # DELETE 2D
        col.prop(point, "is_point_3d_initialised")

        col = layout.column()
        if point.is_point_3d_initialised:
            col.enabled = True
        else:
            col.enabled = False
        # DELETE 3D
        col.prop(point, "is_point_3d_initialised")


class ImagePanel(bpy.types.Panel):
    bl_label = "Add / Change Image"
    bl_idname = "VIEW3D_PT_AddImage"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings

        row = layout.row(align=True)
        row.label(text="Image filepath:")
        row.prop(settings, "image_filepath", text="")

        row = layout.row()
        row.operator("imagematches.add_image")

        row = layout.row()
        row.label(text="Change image:")
        row.prop(settings, "current_image_collection")
        row = layout.row()
        row.operator("imagematches.swap_image")


class PointsPanel(bpy.types.Panel):
    bl_label = "Points"
    bl_idname = "VIEW3D_PT_Points"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings

        row = layout.row(align=True)
        row.label(text="3D model :")
        row.prop(settings, "model", text="")

        if not settings.point_mode_enabled:
            mode_icon = "PLAY"
            mode_txt = 'Point mode'
        else:
            mode_icon = "PAUSE"
            mode_txt = 'Right click or ESC to cancel'
        
        row = layout.row(align=True)
        row.prop(settings, 'point_mode_enabled', text=mode_txt, icon=mode_icon, toggle=True)

        row = layout.row()
        row.template_list("POINT_UL_UI", "Point_List", settings, "current_points", settings, "active_point_index")


class PnpPanel(bpy.types.Panel):
    bl_label = "PNP"
    bl_idname = "VIEW3D_PT_PNP"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings

        col = layout.column(heading="3D Points", align=True)
        col.prop(settings, "points_3d_collection")
        
        col = layout.column(heading="Calibrate", align=True)
        col.prop(settings, "pnp_intrinsics_focal_length", text="Focal Length")
        col.prop(settings, "pnp_intrinsics_principal_point", text="Optical Center")
        row = col.row(align=True).split(factor=0.22)
        row.prop(settings, "pnp_intrinsics_distortion_k1", text="K1")
        row = row.row(align=True).split(factor=0.3)
        row.prop(settings, "pnp_intrinsics_distortion_k2", text="K2")
        row.prop(settings, "pnp_intrinsics_distortion_k3", text="K3 Distortion")
        
        col = layout.column(align=True)
        col.operator("pnp.calibrate_camera", text="Calibrate Camera")
        
        col = layout.column(align=True)
        col.operator("pnp.solve_pnp", text="Solve Camera Pose")
        col.scale_y = 2.0
        
        col = layout.column(align=True)
        col.label(text=settings.pnp_msg)


class ExportPanel(bpy.types.Panel):
    bl_label = "Export"
    bl_idname = "VIEW3D_PT_Export"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings

        row = layout.row(align=True)
        row.label(text="3D model :")
        row.prop(settings, "model", text="")

        row = layout.row(align=True)
        row.label(text="Export filepath :")
        row.prop(settings, "export_filepath", text="")

        row = layout.row()
        row.operator("imagematches.export_matches")


class PNP_OT_install_dependencies(bpy.types.Operator):
    bl_idname = 'pnp.install_dependencies'
    bl_label = 'Install dependencies'
    bl_options = {'REGISTER', 'INTERNAL'}
    bl_description = (
        "Downloads and installs the required python packages for this add-on. "
        "Internet connection is required. Blender may have to be started with "
        "elevated permissions in order to install the package")

    @classmethod
    def poll(self, context):
        # Deactivate when dependencies have been installed
        return not dependencies_installed
    
    def execute(self, context):
        global dependencies_installed

        try:
            dependency.install_pip()
            dependency.install_all_dependencies(dependencies)
            self.report({'INFO'}, 
                        "Successfully installed dependencies")
            dependencies_installed = True

            # If dependencies installed successfully, register rest of addon
            # classes
            register_classes()
            return {"FINISHED"}

        except (subprocess.CalledProcessError, ImportError) as e:
            self.report({"ERROR"}, 
                        f"Failed to install dependencies.\n Error: {e.stderr}")
            print(e.stderr)
            dependencies_installed = False
            return {"CANCELLED"}

        
class PNP_preferences(bpy.types.AddonPreferences):
    bl_label = "Dependencies"
    bl_idname = __package__

    def draw(self, context):
        row = self.layout.row()
        # Check if dependencies are installed
        if not dependencies_installed:
            installation_status_msg = "Dependency Status: OpenCV not found."
        else:
            installation_status_msg = "Dependency Status: OpenCV is installed."
        row.label(text=installation_status_msg)
        row.operator("pnp.install_dependencies", icon="CONSOLE")


# Classes for addon preferences
preferences_classes = [PNP_OT_install_dependencies, PNP_preferences]

# module (name you import with), package (name you install with)
Dependency = namedtuple("Dependency", ["module", "package"])
dependencies = (Dependency(module="cv2", package="opencv-contrib-python"),)
dependencies_installed = False


def register_classes(unregister=False):
    # These classes are imported inside this function (and not at top of doc)
    # as they are dependent on opencv installation
    from .pnp import PNP_OT_calibrate_camera, PNP_OT_pose_camera

    classes = [PointMatch,
               POINT_UL_UI,
               ImageMatchSettings,
               OBJECT_OT_export_matches,
               PNP_OT_calibrate_camera,
               PNP_OT_pose_camera,
               ImagePanel,
               PointsPanel,
               PnpPanel,
               ExportPanel,
               IMAGE_OT_add_image,
               IMAGE_OT_swap_image,
               IMAGE_OT_point_mode,
               IMAGE_OT_add_3d_point,
               IMAGE_OT_add_2d_point,
               IMAGE_OT_delete_3d_point,
               IMAGE_OT_delete_2d_point
               ]
    
    if unregister:
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
        
        del bpy.types.Scene.match_settings
    else:
        for cls in classes:
            bpy.utils.register_class(cls)

        bpy.types.Scene.match_settings = \
            bpy.props.PointerProperty(type=ImageMatchSettings)
    

def register():
    print("registering...")
    
    # Couldn't find a simple way to avoid using a global variable here. During
    # registration access to props / context.scene etc is restricted, so the
    # variables can't be stored there directly.
    global dependencies_installed
    dependencies_installed = False

    # Register classes for addon preferences panel to install dependencies
    for cls in preferences_classes:
        bpy.utils.register_class(cls)

    if dependency.is_available(dependencies):
        dependencies_installed = True
        register_classes()

   
def unregister():
    print("Unregistering...")

    if dependencies_installed:
        register_classes(unregister=True)
    
    for cls in reversed(preferences_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()

