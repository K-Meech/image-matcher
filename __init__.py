bl_info = {
    "name": "Image Matcher",
    "author": "Kimberly Meechan",
    "version": (1, 0, 0),
    "blender": (3, 6, 2),
    "location": "Clip Editor > Tools > Solve > Image Matcher",
    "description": "Matches 2D images to the 3D model (builds on RT Studio's Camera Pnpoint plugin)",
    "warning": "",
    "doc_url": "",
    "category": "Export",
}


import bpy
import subprocess
from collections import namedtuple
from . import export
from . import dependency
from . import ui
from . import props
from . import image


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
    """Addon preferences panel"""

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
    """Register/un-register all addon classes

    Args:
        unregister: Unregisters when true, otherwise registers.
        Defaults to False.
    """

    # pnp is imported inside this function (and not at top of doc)
    # as it is dependent on opencv installation
    from . import pnp

    classes = [
        props.PointMatch,
        ui.POINT_UL_UI,
        props.ImageMatch,
        ui.IMAGE_UL_UI,
        props.ImageMatchSettings,
        export.OBJECT_OT_export_matches,
        pnp.PNP_OT_calibrate_camera,
        pnp.PNP_OT_pose_camera,
        pnp.PNP_OT_reset_camera,
        ui.ImagePanel,
        ui.PointsPanel,
        ui.CalibratePanel,
        ui.SolvePanel,
        ui.CurrentCameraSettings,
        ui.ExportPanel,
        image.IMAGE_OT_add_image,
        image.IMAGE_OT_swap_image,
        image.IMAGE_OT_point_mode,
        image.IMAGE_OT_add_3d_point,
        image.IMAGE_OT_add_2d_point,
        image.IMAGE_OT_delete_3d_point,
        image.IMAGE_OT_delete_2d_point,
        image.IMAGE_OT_toggle_camera_view,
        image.IMAGE_OT_update_3d_point_size,
    ]

    if unregister:
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

        del bpy.types.Scene.match_settings
    else:
        for cls in classes:
            bpy.utils.register_class(cls)

        bpy.types.Scene.match_settings = bpy.props.PointerProperty(
            type=props.ImageMatchSettings
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
