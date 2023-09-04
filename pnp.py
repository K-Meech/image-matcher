""" Adapted from original code from Roger Torm, RT Studios Camera Pnpoint plugin
https://rtstudios.gumroad.com/l/camera_pnpoint """

import bpy
import cv2 as cv
import numpy as np
from mathutils import Matrix, Vector


def get_optical_centre(clip_camera):
    """Get optical centre of given camera"""

    if bpy.app.version < (3, 5, 0):
        optical_centre = clip_camera.principal
    else:
        optical_centre = clip_camera.principal_point_pixels

    return optical_centre


def get_2D_3D_point_coordinates(self, point_matches, clip):
    """Get coordinates of all 2D-3D point matches. Discards any matches with
    only a 2D point or only a 3D point.

    Args:
        point_matches: current point matches
        clip: current Blender movie clip

    Returns:
        Two numpy arrays of equal size - the first being the coordinates of all
        2D points, and the second the coordinates of all 3D points
    """
    size = clip.size
    tracks = clip.tracking.objects[0].tracks

    if not tracks:
        self.report({"ERROR"}, "Please add markers for the 2D points")
        return np.array([]), np.array([])

    points_2d_coords = []
    points_3d_coords = []
    points_ignored = False

    for point_match in point_matches:
        # Only process matches with both 2D and 3D point initialised -
        # rest ignored
        if (
            point_match.is_point_2d_initialised
            and point_match.is_point_3d_initialised
        ):
            points_3d_coords.append(point_match.point_3d.location)

            track = tracks[point_match.point_2d]
            # .co runs from 0 to 1 on each axis of the image, so multiply
            # by image size to get full coordinates
            point_2d_coordinates = [
                track.markers[0].co[0] * size[0],
                size[1] - track.markers[0].co[1] * size[1],
            ]

            points_2d_coords.append(point_2d_coordinates)

        else:
            points_ignored = True

    if points_ignored:
        self.report({"WARNING"}, "Ignoring points with only 2D or only 3D")

    points_2d_coords = np.asarray(points_2d_coords, dtype="double")
    points_3d_coords = np.asarray(points_3d_coords, dtype="double")

    return points_2d_coords, points_3d_coords


def get_distortion_coefficients(self, clip_camera):
    """Get distortion coefficients of given camera as a numpy array of
    np.array([k1, k2, 0, 0, k3])"""

    # take radial distortion parameters:
    if clip_camera.distortion_model == "POLYNOMIAL":
        k1, k2, k3 = clip_camera.k1, clip_camera.k2, clip_camera.k3
    elif clip_camera.distortion_model == "BROWN":
        k1, k2, k3 = (
            clip_camera.brown_k1,
            clip_camera.brown_k2,
            clip_camera.brown_k3,
        )
    else:
        # Unsupported distortion model - just set to defaults of 0
        k1, k2, k3 = 0.0, 0.0, 0.0
        self.report(
            {"WARNING"},
            "Current distortion model is not supported, use Polynomial instead.",
        )

    # construct distortion vector, only k1,k2,k3 (polynomial or brown models)
    distortion_coefficients = np.array([k1, k2, 0, 0, k3])

    return distortion_coefficients


def get_camera_intrinsics(clip_camera, clip_size):
    """Get array of intrinsics for given camera + movie clip size

    Args:
        clip_camera: Blender movie clip camera
        clip_size: Blender movie clip size

    Returns:
        Numpy array of camera intrinsics
    """
    focal = clip_camera.focal_length_pixels
    optical_centre = get_optical_centre(clip_camera)

    # construct camera intrinsics
    camera_intrinsics = np.array(
        [
            [focal, 0, optical_centre[0]],
            [0, focal, clip_size[1] - optical_centre[1]],
            [0, 0, 1],
        ],
        dtype="double",
    )

    return camera_intrinsics


def get_scene_info(self, context):
    """Collect information from the movie clip and its camera, as well as
    2D and 3D points from the current image match

    Args:
        context: Blender context

    Returns:
        self - self from Blender operator
        context - Blender context
        clip - current Blender movie clip
        points_3d_coords - numpy array of 3D point coordinates
        points_2d_coords - numpy array of 2D point coordinates
        camera_intrinsics - numpy array of camera intrinsics
        distortion_coefficients - numpy array of camera distortion coefficients
    """

    settings = context.scene.match_settings
    current_image = settings.image_matches[settings.current_image_name]

    clip = current_image.movie_clip

    # get picture and camera metrics
    size = clip.size
    clip_camera = clip.tracking.camera

    points_2d_coords, points_3d_coords = get_2D_3D_point_coordinates(
        self, current_image.point_matches, clip
    )
    camera_intrinsics = get_camera_intrinsics(clip_camera, size)
    distortion_coefficients = get_distortion_coefficients(self, clip_camera)

    return (
        self,
        context,
        clip,
        points_3d_coords,
        points_2d_coords,
        camera_intrinsics,
        distortion_coefficients,
    )


def solve_pnp(
    self,
    context,
    clip,
    points_3d_coords,
    points_2d_coords,
    camera_intrinsics,
    distortion_coefficients,
):
    """Solve camera pose with OpenCV's PNP solver. Set the current camera
    intrinsics, extrinsics and background image to match

    Args:
        context: Blender context
        clip: Blender movie clip
        points_3d_coords: numpy array of 3D point coordinates
        points_2d_coords: numpy array of 2D point coordinates
        camera_intrinsics: numpy array of camera intrinsics
        distortion_coefficients: numpy array of camera distortion coefficients

    Returns:
        Status for operator - cancelled or finished
    """

    npoints = points_3d_coords.shape[0]
    size = clip.size

    if npoints < 4:
        self.report(
            {"ERROR"},
            "Not enough point pairs, use at least 4 markers to solve a camera pose.",
        )
        return {"CANCELLED"}

    # solve Perspective-n-Point
    ret, rvec, tvec, error = cv.solvePnPGeneric(
        points_3d_coords,
        points_2d_coords,
        camera_intrinsics,
        distortion_coefficients,
        flags=cv.SOLVEPNP_SQPNP,
    )  # TODO: further investigation on other algorithms
    rmat, _ = cv.Rodrigues(rvec[0])

    settings = context.scene.match_settings
    settings.pnp_solve_msg = (
        ("Reprojection Error: %.2f" % error) if ret else "solvePnP failed!"
    )

    # calculate projection errors for each point pair
    print("dbg: calculating projections of 3d points...")
    impoints, jacob = cv.projectPoints(
        points_3d_coords,
        rvec[0],
        tvec[0],
        camera_intrinsics,
        distortion_coefficients,
    )
    print("dbg: projection finished")
    print(impoints)
    print(jacob)

    # get R and T matrices
    # https://blender.stackexchange.com/questions/38009/3x4-camera-matrix-from-blender-camera
    R_world2cv = Matrix(rmat.tolist())
    T_world2cv = Vector(tvec[0])

    # blender camera to opencv camera coordinate conversion
    R_bcam2cv = Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))

    # calculate transform in world coordinates
    R_cv2world = R_world2cv.transposed()
    rot = R_cv2world @ R_bcam2cv
    loc = -1 * R_cv2world @ T_world2cv

    # Set camera intrinsics, extrinsics and background
    current_image = settings.image_matches[settings.current_image_name]
    camera = current_image.camera
    tracking_camera = clip.tracking.camera

    camera_data = camera.data
    camera_data.type = "PERSP"
    camera_data.lens = tracking_camera.focal_length
    camera_data.sensor_width = tracking_camera.sensor_width
    camera_data.sensor_height = (
        tracking_camera.sensor_width * size[1] / size[0]
    )
    render_size = [
        context.scene.render.pixel_aspect_x
        * context.scene.render.resolution_x,
        context.scene.render.pixel_aspect_y
        * context.scene.render.resolution_y,
    ]
    camera_data.sensor_fit = (
        "HORIZONTAL"
        if render_size[0] / render_size[1] <= size[0] / size[1]
        else "VERTICAL"
    )
    refsize = (
        size[0]
        if render_size[0] / render_size[1] <= size[0] / size[1]
        else size[1]
    )

    optical_centre = get_optical_centre(tracking_camera)
    camera_data.shift_x = (size[0] * 0.5 - optical_centre[0]) / refsize
    camera_data.shift_y = (size[1] * 0.5 - optical_centre[1]) / refsize

    camera_data.show_background_images = True
    if not camera_data.background_images:
        background_image = camera_data.background_images.new()
    else:
        background_image = camera_data.background_images[0]
    background_image.source = "MOVIE_CLIP"
    background_image.clip = clip
    background_image.frame_method = "FIT"
    background_image.display_depth = "FRONT"
    background_image.clip_user.use_render_undistorted = True

    camera.matrix_world = Matrix.Translation(loc) @ rot.to_4x4()
    context.scene.camera = camera

    return {"FINISHED"}


def calibrate_camera(
    self,
    context,
    clip,
    points_3d_coords,
    points_2d_coords,
    camera_intrinsics,
    distortion_coefficients,
):
    """Calibrate current tracking camera using openCV. Sets the intrinsics
    that are currently specified in the settings.

    Args:
        context: Blender context
        clip: Blender movie clip
        points_3d_coords: numpy array of 3D point coordinates
        points_2d_coords: numpy array of 2D point coordinates
        camera_intrinsics: numpy array of camera intrinsics
        distortion_coefficients: numpy array of camera distortion coefficients

    Returns:
        Status for operator - cancelled or finished
    """

    settings = context.scene.match_settings
    npoints = points_3d_coords.shape[0]
    size = clip.size

    if npoints < 6:
        self.report(
            {"ERROR"},
            "Not enough point pairs, use at least 6 markers to calibrate a camera.",
        )
        return {"CANCELLED"}

    flags = (
        cv.CALIB_USE_INTRINSIC_GUESS
        + cv.CALIB_FIX_ASPECT_RATIO
        + cv.CALIB_ZERO_TANGENT_DIST
        + (
            cv.CALIB_FIX_PRINCIPAL_POINT
            if not settings.calibrate_principal_point
            else 0
        )
        + (
            cv.CALIB_FIX_FOCAL_LENGTH
            if not settings.calibrate_focal_length
            else 0
        )
        + (cv.CALIB_FIX_K1 if not settings.calibrate_distortion_k1 else 0)
        + (cv.CALIB_FIX_K2 if not settings.calibrate_distortion_k2 else 0)
        + (cv.CALIB_FIX_K3 if not settings.calibrate_distortion_k3 else 0)
    )

    ret, camera_intrinsics, distortion_coefficients, _, _ = cv.calibrateCamera(
        np.asarray([points_3d_coords], dtype="float32"),
        np.asarray([points_2d_coords], dtype="float32"),
        size,
        camera_intrinsics,
        distortion_coefficients,
        flags=flags,
    )

    settings.pnp_calibrate_msg = "Reprojection Error: %.2f" % ret

    # set picture and camera metrics
    tracking_camera = clip.tracking.camera

    if settings.calibrate_focal_length:
        tracking_camera.focal_length_pixels = camera_intrinsics[0][0]

    if settings.calibrate_principal_point:
        optical_centre = [
            camera_intrinsics[0][2],
            size[1] - camera_intrinsics[1][2],
        ]
        if bpy.app.version < (3, 5, 0):
            tracking_camera.principal = optical_centre
        else:
            tracking_camera.principal_point_pixels = optical_centre

    if (
        settings.calibrate_distortion_k1
        or settings.calibrate_distortion_k2
        or settings.calibrate_distortion_k3
    ):
        tracking_camera.k1 = distortion_coefficients[0]
        tracking_camera.k2 = distortion_coefficients[1]
        tracking_camera.k3 = distortion_coefficients[4]
        tracking_camera.brown_k1 = distortion_coefficients[0]
        tracking_camera.brown_k2 = distortion_coefficients[1]
        tracking_camera.brown_k3 = distortion_coefficients[4]

    return {"FINISHED"}


class PNP_OT_pose_camera(bpy.types.Operator):
    """Solve camera extrinsics using available 2D-3D point matches"""

    bl_idname = "pnp.solve_pnp"
    bl_label = "Solve camera extrinsics"
    bl_options = {"UNDO"}

    def execute(self, context):
        settings = context.scene.match_settings

        if settings.model.mode != "OBJECT":
            self.report({"ERROR"}, "Please switch to Object Mode")
            return {"CANCELLED"}

        # call solver
        return solve_pnp(*get_scene_info(self, context))


class PNP_OT_calibrate_camera(bpy.types.Operator):
    """Solve camera intrinsics using available 2D-3D point matches"""

    bl_idname = "pnp.calibrate_camera"
    bl_label = "Solve camera intrinsics"
    bl_options = {"UNDO"}

    def execute(self, context):
        settings = context.scene.match_settings

        if settings.model.mode != "OBJECT":
            self.report({"ERROR"}, "Please switch to Object Mode")
            return {"CANCELLED"}

        # call solver
        return calibrate_camera(*get_scene_info(self, context))
