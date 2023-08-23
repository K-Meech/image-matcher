# Original code from Roger Torm, RT Studios Camera Pnpoint plugin
# https://rtstudios.gumroad.com/l/camera_pnpoint

import bpy
import cv2 as cv
import numpy as np
from mathutils import Matrix, Vector


# get_scene_info collects information from the movie clip and its camera, 
# as well as 2D points and 3D points from the chosen collection
def get_scene_info(self, context):
    settings = context.scene.match_settings

    # get currently loaded movieclip or image
    clip = context.area.spaces.active.clip
    if not clip:
        self.report({'ERROR'}, 'Please load an image in the clip editor')

    # get picture and camera metrics
    size = clip.size
    clip_camera = clip.tracking.camera
    focal = clip_camera.focal_length_pixels
    if bpy.app.version < (3, 5, 0):
        optical_centre = clip_camera.principal
    else:
        optical_centre = clip_camera.principal_point_pixels
    # take radial distortion parameters: 
    if clip_camera.distortion_model == 'POLYNOMIAL':
        k1, k2, k3 = clip_camera.k1, clip_camera.k2, clip_camera.k3
    elif clip_camera.distortion_model == 'BROWN':
        k1, k2, k3 = clip_camera.brown_k1, clip_camera.brown_k2, clip_camera.brown_k3
    else:
        k1, k2, k3 = 0.0, 0.0, 0.0
        self.report({'WARNING'}, 'Current distortion model is not supported, use Polynomial instead.')

    # get current frame to retrieve marker locations
    current_frame = bpy.data.scenes[0].frame_current - bpy.data.scenes[0].frame_start

    # get list of tracks and retrieve marker positions at current frame
    points_2d = []
    tracks = clip.tracking.tracks
    if not tracks:
        self.report({'ERROR'}, 'Please add markers for the 2D points')
        l2d = 0
    else:
        for track in sorted(tracks, key = lambda o: o.name):
            points_2d.append([track.markers[current_frame].co[0]*size[0],
                             size[1]-track.markers[current_frame].co[1]*size[1]])
        points_2d = np.asarray(points_2d, dtype='double')
        l2d = points_2d.shape[0]

    # retrieve 3D points from scene objects
    points_3d = []
    current_image = settings.image_matches[settings.current_image_name]
    collection_3d = current_image.points_3d_collection
    if collection_3d == None:
        self.report({'ERROR'}, 'Please specify a collection for the 3D points')
        l3d = 0
    else: 
        for point in sorted(collection_3d.all_objects, key = lambda o: o.name):
            points_3d.append(point.location)
        points_3d = np.asarray(points_3d, dtype='double')
        l3d = points_3d.shape[0]

    # check point list length compatibility
    n_points = l2d
    if l2d > l3d: 
        points_2d = points_2d[:l3d,:]
        self.report({'WARNING'}, 'Ignoring extra 2D points')
        n_points = l3d
    elif l2d < l3d: 
        points_3d = points_3d[:l2d,:]
        self.report({'WARNING'}, 'Ignoring extra 3D points')

    # construct camera intrinsics
    camera_intrinsics = np.array([ [focal, 0, optical_centre[0]],
                    [0, focal, size[1]-optical_centre[1]],
                    [0, 0, 1] ], dtype='double')

    # construct distortion vector, only k1,k2,k3 (polynomial or brown models)
    distortion_coefficients = np.array([k1, k2, 0, 0, k3])
    
    return self, context, clip, points_3d, points_2d, \
        camera_intrinsics, distortion_coefficients, size, n_points


# main PnP solver function
def solve_pnp(self, context, clip, points_3d, points_2d, camera_intrinsics, 
              distortion_coefficients, size, npoints):
    if npoints < 4:
        self.report({'ERROR'}, 'Not enough point pairs, use at least 4 markers to solve a camera pose.')
        return {'CANCELLED'}
    
    # solve Perspective-n-Point
    ret, rvec, tvec, error = cv.solvePnPGeneric(
        points_3d,
        points_2d,
        camera_intrinsics,
        distortion_coefficients,
        flags=cv.SOLVEPNP_SQPNP) # TODO: further investigation on other algorithms             
    rmat, _ = cv.Rodrigues(rvec[0])

    settings = context.scene.match_settings
    settings.pnp_msg = \
        ("Reprojection Error: %.2f" %error) if ret else "solvePnP failed!"
    
    # calculate projection errors for each point pair
    print('dbg: calculating projections of 3d points...')
    impoints, jacob = cv.projectPoints(points_3d, rvec[0], tvec[0],
                                       camera_intrinsics,
                                       distortion_coefficients)
    print('dbg: projection finished')
    print(impoints)
    print(jacob)
    
    # get R and T matrices
    # https://blender.stackexchange.com/questions/38009/3x4-camera-matrix-from-blender-camera
    R_world2cv = Matrix(rmat.tolist())
    T_world2cv = Vector(tvec[0])

    # blender camera to opencv camera coordinate conversion
    R_bcam2cv = Matrix(
        ((1, 0, 0),
         (0, -1, 0),
         (0, 0, -1)))

    # calculate transform in world coordinates
    R_cv2world = R_world2cv.transposed()
    rot = R_cv2world @ R_bcam2cv
    loc = -1 * R_cv2world @ T_world2cv

    # Create new camera or use existing
    # check if active object is a camera, if so, assume user wants to set it up, otherwise create a new camera
    if context.active_object == None or context.active_object.type != 'CAMERA': # add a new one
        bpy.ops.object.add(type='CAMERA')
        bpy.context.object.name = clip.name 

    # Set camera intrinsics, extrinsics and background
    camera = context.object
    camera_data = camera.data
    camera_data.type = 'PERSP'
    camera_data.lens = clip.tracking.camera.focal_length
    camera_data.sensor_width = clip.tracking.camera.sensor_width
    camera_data.sensor_height = clip.tracking.camera.sensor_width*size[1]/size[0]
    render_size = [
        context.scene.render.pixel_aspect_x * context.scene.render.resolution_x,
        context.scene.render.pixel_aspect_y * context.scene.render.resolution_y]
    camera_data.sensor_fit = 'HORIZONTAL' if render_size[0]/render_size[1] <= size[0]/size[1] else 'VERTICAL'
    refsize = size[0] if render_size[0]/render_size[1] <= size[0]/size[1] else size[1]
    if bpy.app.version < (3, 5, 0):
        camera_data.shift_x = (size[0]*0.5 - clip.tracking.camera.principal[0])/refsize
        camera_data.shift_y = (size[1]*0.5 - clip.tracking.camera.principal[1])/refsize
    else:
        camera_data.shift_x = (size[0]*0.5 - clip.tracking.camera.principal_point_pixels[0])/refsize
        camera_data.shift_y = (size[1]*0.5 - clip.tracking.camera.principal_point_pixels[1])/refsize
    
    camera_data.show_background_images = True
    if not camera_data.background_images: 
        background_image = camera_data.background_images.new()
    else: 
        background_image = camera_data.background_images[0]
    background_image.source = 'MOVIE_CLIP'
    background_image.clip = clip
    background_image.frame_method = 'FIT' 
    background_image.display_depth = 'FRONT'
    background_image.clip_user.use_render_undistorted = True
    
    camera.matrix_world = Matrix.Translation(loc) @ rot.to_4x4()
    context.scene.camera = camera
    
    return {'FINISHED'}


# main Calibration solver function
def calibrate_camera(self, context, clip, points3d, points2d,
                     camera_intrinsics, distortion_coefficients,
                     size, npoints): 
    
    settings = context.scene.match_settings 

    if npoints < 6:
        self.report({'ERROR'},
                    'Not enough point pairs, use at least 6 markers to calibrate a camera.')
        return {'CANCELLED'}

    flags = (
        cv.CALIB_USE_INTRINSIC_GUESS + 
        cv.CALIB_FIX_ASPECT_RATIO + 
        cv.CALIB_ZERO_TANGENT_DIST + 
        (cv.CALIB_FIX_PRINCIPAL_POINT if not settings.pnp_intrinsics_principal_point else 0) + 
        (cv.CALIB_FIX_FOCAL_LENGTH if not settings.pnp_intrinsics_focal_length else 0) + 
        (cv.CALIB_FIX_K1 if not settings.pnp_intrinsics_distortion_k1 else 0) + 
        (cv.CALIB_FIX_K2 if not settings.pnp_intrinsics_distortion_k2 else 0) + 
        (cv.CALIB_FIX_K3 if not settings.pnp_intrinsics_distortion_k3 else 0))
    
    ret, camera_intrinsics, distortion_coefficients, _, _ = \
        cv.calibrateCamera(
            np.asarray([points3d], dtype='float32'),
            np.asarray([points2d], dtype='float32'),
            size,
            camera_intrinsics,
            distortion_coefficients,
            flags=flags)
         
    settings.pnp_msg = ("Reprojection Error: %.2f" %ret)
    
    # set picture and camera metrics
    if settings.pnp_intrinsics_focal_length:
        clip.tracking.camera.focal_length_pixels = camera_intrinsics[0][0] 
    if settings.pnp_intrinsics_principal_point:
        if bpy.app.version < (3, 5, 0):
            clip.tracking.camera.principal = \
                [camera_intrinsics[0][2], size[1]-camera_intrinsics[1][2]]
        else:
            clip.tracking.camera.principal_point_pixels = \
                [camera_intrinsics[0][2], size[1]-camera_intrinsics[1][2]]
    if settings.pnp_intrinsics_distortion_k1 or settings.pnp_intrinsics_distortion_k2 or settings.pnp_intrinsics_distortion_k3:
        clip.tracking.camera.k1 = distortion_coefficients[0]
        clip.tracking.camera.k2 = distortion_coefficients[1]
        clip.tracking.camera.k3 = distortion_coefficients[4]
        clip.tracking.camera.brown_k1 = distortion_coefficients[0]
        clip.tracking.camera.brown_k2 = distortion_coefficients[1]
        clip.tracking.camera.brown_k3 = distortion_coefficients[4]

    return {'FINISHED'}


class PNP_OT_pose_camera(bpy.types.Operator):
    bl_idname = "pnp.solve_pnp"
    bl_label = "Solve camera extrinsics"
    bl_options = {'UNDO'}
    bl_description = "Solve camera extrinsics using available markers and 3D points"
    
    def execute(self, context):
        if context.object.mode != 'OBJECT':
            self.report({'ERROR'}, 'Please switch to Object Mode')
            return {'CANCELLED'}
        
        # call solver
        return solve_pnp(*get_scene_info(self, context))


class PNP_OT_calibrate_camera(bpy.types.Operator):
    bl_idname = "pnp.calibrate_camera"
    bl_label = "Solve camera intrinsics"
    bl_options = {'UNDO'}
    bl_description = "Solve camera intrinsics using available markers and 3D points"
    
    def execute(self, context):
        if context.object.mode != 'OBJECT':
            self.report({'ERROR'}, 'Please switch to Object Mode')
            return {'CANCELLED'}
        
        # call solver
        return calibrate_camera(*get_scene_info(self, context))
