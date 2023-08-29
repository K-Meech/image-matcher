import bpy


def current_image_initialised(context):
    settings = context.scene.match_settings
    return settings.current_image_name != ""


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