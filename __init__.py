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
from .image import (
    IMAGE_OT_add_image,
    IMAGE_OT_swap_image,
    IMAGE_OT_point_mode,
    IMAGE_OT_add_3d_point,
    IMAGE_OT_add_2d_point,
    IMAGE_OT_delete_3d_point,
    IMAGE_OT_delete_2d_point,
    IMAGE_OT_toggle_camera_view,
    IMAGE_OT_update_3d_point_size,
)


def update_active_point_match(self, context):
    active_point_index = self.active_point_index
    active_point_match = self.point_matches[active_point_index]

    # Select the current 3d point
    bpy.ops.object.select_all(action="DESELECT")
    if active_point_match.is_point_3d_initialised:
        active_point_match.point_3d.select_set(True)
        bpy.context.view_layer.objects.active = active_point_match.point_3d

    # Select the current 2d point
    bpy.ops.clip.select_all(action="DESELECT")
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
    ensures that e.g. as 3D points are added, they immediately show up in the
    UI list"""
    pass


def current_image_initialised(context):
    settings = context.scene.match_settings
    return settings.current_image_name != ""


export_types = [("BLENDER", "Blender", "", 1), ("THREEJS", "ThreeJS", "", 2)]


class PointMatch(bpy.types.PropertyGroup):
    """Group of properties representing a 2D-3D point match"""

    is_point_2d_initialised: bpy.props.BoolProperty(
        name="2D point", description="Is 2D point initialised?", default=False
    )

    is_point_3d_initialised: bpy.props.BoolProperty(
        name="3D point",
        description="Is 3D point initialised?",
        default=False,
        update=force_redraw,
    )

    point_3d: bpy.props.PointerProperty(name="3D point", type=bpy.types.Object)

    # Name of track for this 2D point. Don't seem to be
    # able to directly store a pointer to the track
    point_2d: bpy.props.StringProperty(
        name="Name of point 2D track",
        default="",
        description="Name of track for this 2D point",
    )


class ImageMatch(bpy.types.PropertyGroup):
    """Group of properties representing an image to be matched"""

    # Name of image collection/clip - may be a shortened version
    # of the full name as Blender has a character limit
    name: bpy.props.StringProperty(
        name="Name of image collection/clip",
        default="",
        description="Name of image collection/clip",
    )

    full_name: bpy.props.StringProperty(
        name="Full filename of image",
        default="",
        description="Full filename of image",
    )

    movie_clip: bpy.props.PointerProperty(
        name="Movie clip for image",
        description="Move clip for image",
        type=bpy.types.MovieClip,
    )

    camera: bpy.props.PointerProperty(
        name="Camera",
        description="Camera for this image",
        type=bpy.types.Object,
    )

    image_collection: bpy.props.PointerProperty(
        name="Image collection",
        description="Collection for image",
        type=bpy.types.Collection,
    )

    points_3d_collection: bpy.props.PointerProperty(
        name="3D points collection",
        description="Collection for 3D points of image",
        type=bpy.types.Collection,
    )

    point_matches: bpy.props.CollectionProperty(
        type=PointMatch, name="Current points", description="Current points"
    )

    active_point_index: bpy.props.IntProperty(
        name="Active point index",
        description="Active point index",
        default=0,
        update=update_active_point_match,
    )


class ImageMatchSettings(bpy.types.PropertyGroup):
    export_filepath: bpy.props.StringProperty(
        name="Export filepath",
        default="",
        description="Define the export filepath for image matches",
        subtype="FILE_PATH",
    )

    model: bpy.props.PointerProperty(
        name="3D model", description="3D model", type=bpy.types.Object
    )

    image_match_collection: bpy.props.PointerProperty(
        name="Image match collection",
        description="Collection for image match results",
        type=bpy.types.Collection,
    )

    image_match_collection_name: bpy.props.StringProperty(
        name="Image match collection name",
        description="Name of collection for image match results",
        default="image-match",
    )

    image_matches: bpy.props.CollectionProperty(
        type=ImageMatch,
        name="Current image matches",
        description="Current image matches",
    )

    active_image_index: bpy.props.IntProperty(
        name="Active image index", description="Active image index", default=0
    )

    current_image_name: bpy.props.StringProperty(
        name="Current image name", description="Current image name", default=""
    )

    points_3d_collection_name: bpy.props.StringProperty(
        name="3D points collection name",
        description="Name for collection of 3D points",
        default="points-3d",
    )

    point_3d_display_size: bpy.props.FloatProperty(
        name="Point 3D display size",
        description="Display size of empty sphere representing 3D point",
        default=0.1,
    )

    calibrate_focal_length: bpy.props.BoolProperty(
        name="Calibrate focal length",
        description="Whether to calibrate the focal length",
        default=True,
    )

    calibrate_principal_point: bpy.props.BoolProperty(
        name="Calibrate optical center",
        description="Whether to calibrate the optical center",
        default=False,
    )

    calibrate_distortion_k1: bpy.props.BoolProperty(
        name="Calibrate distortion K1",
        description="Whether to calibrate radial distortion K1",
        default=False,
    )

    calibrate_distortion_k2: bpy.props.BoolProperty(
        name="Calibrate distortion K2",
        description="Whether to calibrate radial distortion K2",
        default=False,
    )

    calibrate_distortion_k3: bpy.props.BoolProperty(
        name="Calibrate distortion K3",
        description="Whether to calibrate radial distortion K3",
        default=False,
    )

    pnp_calibrate_msg: bpy.props.StringProperty(
        name="Information",
        description="Calibration Output Message",
        default="",
    )

    pnp_solve_msg: bpy.props.StringProperty(
        name="Information", description="Solver Output Message", default=""
    )

    image_filepath: bpy.props.StringProperty(
        name="Image filepath",
        default="",
        description="Define the import filepath for image",
        subtype="FILE_PATH",
    )

    point_mode_enabled: bpy.props.BoolProperty(
        name="Point mode enabled",
        description="Point mode enabled",
        default=False,
        update=force_redraw,
    )

    export_type: bpy.props.EnumProperty(
        name="Export type", description="Export type", items=export_types
    )


class POINT_UL_UI(bpy.types.UIList):
    """UI for point list"""

    def draw_item(
        self,
        context,
        layout,
        data,
        point,
        icon,
        active_data,
        active_propname,
        index,
    ):
        icon = "EMPTY_DATA"

        row = layout.row()

        col = layout.column()
        col.label(text=f"{index + 1}", icon=icon)

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


class IMAGE_UL_UI(bpy.types.UIList):
    """UI for image list"""

    def draw_item(
        self,
        context,
        layout,
        data,
        image,
        icon,
        active_data,
        active_propname,
        index,
    ):
        settings = context.scene.match_settings

        icon = "IMAGE_PLANE"
        row = layout.row()

        col = layout.column()

        is_image_active = image.name == settings.current_image_name
        swap_operator = col.operator(
            "imagematches.swap_image",
            text="",
            icon=icon,
            depress=is_image_active,
        )
        swap_operator.image_name = image.name

        col = layout.column()
        col.label(text=image.name)


class ImagePanel(bpy.types.Panel):
    bl_label = "Add / Change Image"
    bl_idname = "CLIP_PT_AddImage"
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
        row.label(text="Loaded images:")

        row = layout.row()
        row.template_list(
            "IMAGE_UL_UI",
            "Image_List",
            settings,
            "image_matches",
            settings,
            "active_image_index",
            rows=3,
        )


class PointsPanel(bpy.types.Panel):
    bl_label = "Points"
    bl_idname = "CLIP_PT_Points"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"

    @classmethod
    def poll(self, context):
        return current_image_initialised(context)

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings

        row = layout.row(align=True)
        row.label(text="3D model :")
        row.prop(settings, "model", text="")

        row = layout.row(align=True).split(factor=0.7, align=True)
        row.prop(settings, "point_3d_display_size", text="3D point size")
        row.operator("imagematches.update_3d_point_size", text="Update")
        # Bit of space between the display size and point mode
        row = layout.row()

        row = layout.row()
        row.label(text="Click to add, Ctrl + click to delete")

        if not settings.point_mode_enabled:
            mode_icon = "PLAY"
            mode_txt = "Point mode"
        else:
            mode_icon = "PAUSE"
            mode_txt = "Right click or ESC to cancel"

        row = layout.row(align=True)
        row.operator(
            "imagematches.point_mode",
            text=mode_txt,
            icon=mode_icon,
            depress=settings.point_mode_enabled,
        )

        row = layout.row()
        current_image = settings.image_matches[settings.current_image_name]
        row.template_list(
            "POINT_UL_UI",
            "Point_List",
            current_image,
            "point_matches",
            current_image,
            "active_point_index",
        )


class CurrentCameraSettings(bpy.types.Panel):
    bl_label = "Current camera settings"
    bl_idname = "CLIP_PT_PNP_Current_Settings"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"

    bl_parent_id = "CLIP_PT_PNP_Calibrate"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        settings = context.scene.match_settings
        current_image = settings.image_matches[settings.current_image_name]
        camera = current_image.movie_clip.tracking.camera

        col = layout.column()

        # Same as layout in right panel of clip editor under Track >
        # Camera > Lens
        if camera.units == "MILLIMETERS":
            col.prop(camera, "focal_length")
        else:
            col.prop(camera, "focal_length_pixels")
        col.prop(camera, "units", text="Units")

        col = layout.column()
        col.prop(camera, "principal_point", text="Optical Center")

        col = layout.column()
        col.prop(camera, "distortion_model", text="Lens Distortion")
        if camera.distortion_model == "POLYNOMIAL":
            col = layout.column(align=True)
            col.prop(camera, "k1")
            col.prop(camera, "k2")
            col.prop(camera, "k3")
        elif camera.distortion_model == "DIVISION":
            col = layout.column(align=True)
            col.prop(camera, "division_k1")
            col.prop(camera, "division_k2")
        elif camera.distortion_model == "NUKE":
            col = layout.column(align=True)
            col.prop(camera, "nuke_k1")
            col.prop(camera, "nuke_k2")
        elif camera.distortion_model == "BROWN":
            col = layout.column(align=True)
            col.prop(camera, "brown_k1")
            col.prop(camera, "brown_k2")
            col.prop(camera, "brown_k3")
            col.prop(camera, "brown_k4")
            col.separator()
            col.prop(camera, "brown_p1")
            col.prop(camera, "brown_p2")


class CalibratePanel(bpy.types.Panel):
    bl_label = "PNP - calibrate camera"
    bl_idname = "CLIP_PT_PNP_Calibrate"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(self, context):
        return current_image_initialised(context)

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings

        col = layout.column(heading="Calibrate", align=True)
        col.prop(settings, "calibrate_focal_length", text="Focal Length")
        col.prop(settings, "calibrate_principal_point", text="Optical Center")
        row = col.row(align=True).split(factor=0.22)
        row.prop(settings, "calibrate_distortion_k1", text="K1")
        row = row.row(align=True).split(factor=0.3)
        row.prop(settings, "calibrate_distortion_k2", text="K2")
        row.prop(settings, "calibrate_distortion_k3", text="K3 Distortion")

        col = layout.column(align=True)
        col.operator("pnp.calibrate_camera", text="Calibrate Camera")

        row = layout.row()
        row.label(text=settings.pnp_calibrate_msg)


class SolvePanel(bpy.types.Panel):
    bl_label = "PNP - Solve Pose"
    bl_idname = "CLIP_PT_PNP_Solve"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(self, context):
        return current_image_initialised(context)

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings
        current_image = settings.image_matches[settings.current_image_name]

        row = layout.row()
        row.operator("pnp.solve_pnp", text="Solve Camera Pose")
        row.scale_y = 2.0

        row = layout.row()
        row.label(text=settings.pnp_solve_msg)

        row = layout.row()
        row.operator(
            "imagematches.toggle_camera",
            text="Toggle camera view",
            icon="VIEW_CAMERA",
        )
        row = layout.row()
        row.prop(
            current_image.camera.data,
            "show_background_images",
            text="Show matched image",
        )
        row = layout.row()
        row.prop(
            current_image.camera.data.background_images[0],
            "alpha",
            text="Image opacity",
        )


class ExportPanel(bpy.types.Panel):
    bl_label = "Export"
    bl_idname = "CLIP_PT_Export"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(self, context):
        return current_image_initialised(context)

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings

        row = layout.row(align=True)
        row.label(text="3D model :")
        row.prop(settings, "model", text="")

        row = layout.row(align=True)
        row.label(text="Export filepath :")
        row.prop(settings, "export_filepath", text="")

        row = layout.row(align=True)
        row.label(text="Export type :")
        row.prop(settings, "export_type", text="")

        row = layout.row()
        row.operator("imagematches.export_matches")


class PNP_OT_install_dependencies(bpy.types.Operator):
    bl_idname = "pnp.install_dependencies"
    bl_label = "Install dependencies"
    bl_options = {"REGISTER", "INTERNAL"}
    bl_description = (
        "Downloads and installs the required python packages for this add-on. "
        "Internet connection is required. Blender may have to be started with "
        "elevated permissions in order to install the package"
    )

    @classmethod
    def poll(self, context):
        # Deactivate when dependencies have been installed
        return not dependencies_installed

    def execute(self, context):
        global dependencies_installed

        try:
            dependency.install_pip()
            dependency.install_all_dependencies(dependencies)
            self.report({"INFO"}, "Successfully installed dependencies")
            dependencies_installed = True

            # If dependencies installed successfully, register rest of addon
            # classes
            register_classes()
            return {"FINISHED"}

        except (subprocess.CalledProcessError, ImportError) as e:
            self.report(
                {"ERROR"},
                f"Failed to install dependencies.\n Error: {e.stderr}",
            )
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

    classes = [
        PointMatch,
        POINT_UL_UI,
        ImageMatch,
        IMAGE_UL_UI,
        ImageMatchSettings,
        OBJECT_OT_export_matches,
        PNP_OT_calibrate_camera,
        PNP_OT_pose_camera,
        ImagePanel,
        PointsPanel,
        CalibratePanel,
        SolvePanel,
        CurrentCameraSettings,
        ExportPanel,
        IMAGE_OT_add_image,
        IMAGE_OT_swap_image,
        IMAGE_OT_point_mode,
        IMAGE_OT_add_3d_point,
        IMAGE_OT_add_2d_point,
        IMAGE_OT_delete_3d_point,
        IMAGE_OT_delete_2d_point,
        IMAGE_OT_toggle_camera_view,
        IMAGE_OT_update_3d_point_size,
    ]

    if unregister:
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

        del bpy.types.Scene.match_settings
    else:
        for cls in classes:
            bpy.utils.register_class(cls)

        bpy.types.Scene.match_settings = bpy.props.PointerProperty(
            type=ImageMatchSettings
        )


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
