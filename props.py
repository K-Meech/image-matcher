import bpy


def force_redraw(self, context):
    """This empty update function makes Blender re-draw the panel, which
    ensures that e.g. as 3D points are added, they immediately show up in the
    UI list"""
    pass


def update_active_point_match(self, context):
    """When a new point match is selected, select the corresponding 2D and
    3D point"""

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
    """Group of properties representing overall settings for this plugin"""

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
        default="Reprojection Error: -",
    )

    pnp_solve_msg: bpy.props.StringProperty(
        name="Information", 
        description="Solver Output Message", 
        default="Reprojection Error: -"
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
