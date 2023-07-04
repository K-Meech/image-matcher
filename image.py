import bpy
import os
from bpy_extras import view3d_utils
from mathutils import Vector


def open_movie_clip(movie_clip):
    for area in bpy.context.screen.areas:
        if area.type == 'CLIP_EDITOR':
            area.spaces.active.clip = movie_clip


class IMAGE_OT_add_image(bpy.types.Operator):
    """Add a new image"""
    bl_idname = "imagematches.add_image"
    bl_label = "Add image"
    # bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.match_settings
        collection_name = settings.collection

        # Create collection to hold all image match results 
        # (if doesn't already exist)
        if collection_name not in bpy.data.collections:
            result_collection = bpy.data.collections.new(collection_name)
            context.scene.collection.children.link(result_collection)
        else:
            result_collection = bpy.data.collections[collection_name]

        if settings.image_filepath == "":
            self.report({'ERROR'}, 'Please input image filepath')
            return {'CANCELLED'}
        
        image_name = os.path.basename(os.path.normpath(settings.image_filepath))

        if image_name in bpy.data.movieclips:
            self.report({'ERROR'}, 'Image of same name already loaded')
            return {'CANCELLED'}
        
        bpy.data.movieclips.load(settings.image_filepath)
        movie_clip = bpy.data.movieclips.get(image_name)

        # Fake user so clip won't be deleted if not referenced in blend file
        movie_clip.use_fake_user = True

        open_movie_clip(movie_clip)
        
        # Collection for this specific image
        image_name_no_extension = os.path.splitext(image_name)[0]
        image_collection = bpy.data.collections.new(image_name_no_extension)
        result_collection.children.link(image_collection)

        # Collection for 3D points
        point_collection = bpy.data.collections.new(settings.points_collection_name)
        image_collection.children.link(point_collection)

        camera_data = bpy.data.cameras.new(name='Camera')
        camera_data.show_background_images = True
        
        # Set up background image
        if not camera_data.background_images: 
            background_image = camera_data.background_images.new()
        else: 
            background_image = camera_data.background_images[0]
        background_image.source = 'MOVIE_CLIP'
        background_image.clip = movie_clip
        background_image.frame_method = 'FIT' 
        background_image.display_depth = 'FRONT'
        background_image.clip_user.use_render_undistorted = True

        camera_object = bpy.data.objects.new('Camera', camera_data)
        image_collection.objects.link(camera_object)

        settings.current_image_collection = image_collection

        return {'FINISHED'}
    

class IMAGE_OT_swap_image(bpy.types.Operator):
    """Swap active image"""
    bl_idname = "imagematches.swap_image"
    bl_label = "Swap image"
    # bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.match_settings
        result_collection = bpy.data.collections[settings.collection]

        if settings.current_image_collection is None:
            self.report({'ERROR'}, 'Please choose an image')
            return {'CANCELLED'}
        
        if settings.current_image_collection.name not in result_collection.children:
            self.report({'ERROR'}, 'Image collection not in results collection')
            return {'CANCELLED'}
        
        camera = None
        for object in settings.current_image_collection.objects:
            if object.type == "CAMERA":
                camera = object
                break

        if camera is None:
            self.report({'ERROR'}, 'No camera found in image collection')
            return {'CANCELLED'}
        
        movie_clip = camera.data.background_images[0].clip
        open_movie_clip(movie_clip)

        return {'FINISHED'}
    

# Based on blender template - operator modal view 3D raycast   

# Region vs region coordinate
def coordinates_within_region(region, region_coordinate):
    if 0 <= region_coordinate[0] <= region.width and 0 <= region_coordinate[1] <= region.height:
        # print("in")
        return True
    else:
        # print("out")
        return False
    

# Region vs global coordinates
def coordinates_within_region_bounds(region, coordinate):
    if (region.x < coordinate[0] < region.x + region.width 
        and region.y < coordinate[1] < region.y + region.height):
        print("in region")
        return True
    else:
        print("out region")
        return False
    

def find_area(context, area_type):
    # Find window/area/region corresponding to main window of given area type
    selected_window = None
    selected_area = None
    selected_region = None

    for window in context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == area_type:
                selected_area = area
                selected_window = window
                break
            
    if selected_area is not None:
        selected_region = find_region(selected_area)

    return (selected_window, selected_area, selected_region)


def find_region(area):
    """Find main view window of area"""
    for region in area.regions:
        if region.type == "WINDOW":
            return region


def visible_objects_and_duplis(context):
    """Loop over (object, matrix) pairs (mesh only)"""

    depsgraph = context.evaluated_depsgraph_get()
    for dup in depsgraph.object_instances:
        if dup.is_instance:  # Real dupli instance
            obj = dup.instance_object
            yield (obj, dup.matrix_world.copy())
        else:  # Usual object
            obj = dup.object
            yield (obj, obj.matrix_world.copy())


def empties_in_collection(collection):
    """Loop over (object, matrix) pairs (mesh only)"""

    for obj in collection.objects:
        if obj.type == "EMPTY":
            yield (obj, obj.matrix_world.copy())


def obj_ray_cast(ray_origin, ray_target, obj, matrix):
    """Wrapper for ray casting that moves the ray into object space"""

    # get the ray relative to the object
    matrix_inv = matrix.inverted()
    ray_origin_obj = matrix_inv @ ray_origin
    ray_target_obj = matrix_inv @ ray_target
    ray_direction_obj = ray_target_obj - ray_origin_obj

    # cast the ray
    success, location, normal, face_index = obj.ray_cast(ray_origin_obj, ray_direction_obj)

    if success:
        return location, normal, face_index
    else:
        return None, None, None


class IMAGE_OT_add_3d_point(bpy.types.Operator):
    """Adds point to 3D view corresponding to given global point coordinates"""

    bl_idname = "imagematches.add_3d_point"
    bl_label = "Add 3D point"
    # bl_options = {'REGISTER', 'UNDO'}

    point_x: bpy.props.FloatProperty(
        name='Mouse x', 
        description='Mouse x'
    )

    point_y: bpy.props.FloatProperty(
        name='Mouse y', 
        description='Mouse y'
    )

    def execute(self, context):
        """Run this function on left mouse, execute the ray cast"""

        settings = context.scene.match_settings
        model = settings.model
        if model is None:
            self.report({'WARNING'}, "No 3D model selected")
            return {'CANCELLED'}

        region = context.region
        rv3d = context.region_data
        
        # Coordinates within region are global coordinates - region location
        region_coord = self.point_x - region.x, self.point_y - region.y

        # get the ray from the viewport and mouse
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, region_coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, region_coord)

        ray_target = ray_origin + view_vector

        # cast rays and find hit
        best_hit = None
        matrix = model.matrix_world.copy()

        if model.type == 'MESH':
            hit, normal, face_index = obj_ray_cast(ray_origin, ray_target, model, matrix)
            if hit is not None:
                best_hit = matrix @ hit

                empty = bpy.data.objects.new("empty", None)
                empty.empty_display_type = "SPHERE"
                empty.empty_display_size = 0.1
                empty.location = best_hit
                
                image_collection = settings.current_image_collection
                point_collection = image_collection.children[settings.points_collection_name]
                point_collection.objects.link(empty)

        return {'FINISHED'}
    

class IMAGE_OT_delete_3d_point(bpy.types.Operator):
    """Delete point in 3D view corresponding to given global point coordinates"""

    bl_idname = "imagematches.delete_3d_point"
    bl_label = "Delete 3D point"
    # bl_options = {'REGISTER', 'UNDO'}

    point_x: bpy.props.FloatProperty(
        name='Mouse x', 
        description='Mouse x'
    )

    point_y: bpy.props.FloatProperty(
        name='Mouse y', 
        description='Mouse y'
    )

    def execute(self, context):
        """Run this function on left mouse, execute the ray cast"""

        region = context.region
        rv3d = context.region_data
        settings = context.scene.match_settings

        image_collection = settings.current_image_collection
        point_collection = image_collection.children[settings.points_collection_name]

        # Coordinates within region are global coordinates - region location
        region_coord = self.point_x - region.x, self.point_y - region.y

        for empty, matrix in empties_in_collection(point_collection):
            # Coordinate of empty in 2D region
            empty_region_coord = view3d_utils.location_3d_to_region_2d(region, rv3d, empty.location)

            # Get radius of the empty sphere (in 2D coords).
            # First, get vector of current view in 3D space. Then add a vector 
            # of length == empty display size in a direction orthogonal to 
            # this (i.e. get a point on the edge of the sphere, in the 3D 
            # plane corresponding to the current 2D view). Convert this back to
            # 2D space and get distance between this and the empty centre.
            view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, empty_region_coord)
            orthogonal_vector = view_vector.orthogonal()
            orthogonal_vector = orthogonal_vector.normalized()
            empty_edge_point = empty.location + (orthogonal_vector*empty.empty_display_size)

            empty_edge_region_coord = view3d_utils.location_3d_to_region_2d(region, rv3d, empty_edge_point)
            region_radius = (empty_region_coord - empty_edge_region_coord).length

            # Use a bounding box of width == diameter of empty sphere to detect
            # clicks inside
            empty_min_x = empty_region_coord[0] - region_radius
            empty_max_x = empty_region_coord[0] + region_radius
            empty_min_y = empty_region_coord[1] - region_radius
            empty_max_y = empty_region_coord[1] + region_radius 

            if empty_min_x <= region_coord[0] <= empty_max_x and \
                empty_min_y <= region_coord[1] <= empty_max_y:
                bpy.data.objects.remove(empty, do_unlink=True)
                break
        
        return {'FINISHED'}


class IMAGE_OT_add_2d_point(bpy.types.Operator):
    """Adds point to clip editor corresponding to given global point coordinates"""

    bl_idname = "imagematches.add_2d_point"
    bl_label = "Add 2D point"
    # bl_options = {'REGISTER', 'UNDO'}

    point_x: bpy.props.FloatProperty(
        name='Mouse x', 
        description='Mouse x'
    )

    point_y: bpy.props.FloatProperty(
        name='Mouse y', 
        description='Mouse y'
    )

    def execute(self, context):
        """Add point to clip editor"""

        region = context.region

        # Coordinates within region are global coordinates - region location
        region_coord = self.point_x - region.x, self.point_y - region.y

        # region_coord = event.mouse_region_x, event.mouse_region_y
        # Coordinates within image - 0 to 1 on each axis
        view_coord = region.view2d.region_to_view(region_coord[0], region_coord[1])

        # Only add markers if lie within the bounds of the image so (0, 1)
        if 0 <= view_coord[0] <= 1 and 0 <= view_coord[1] <= 1:
            current_movie_clip = context.edit_movieclip
            current_frame = context.scene.frame_current
            
            tracks = current_movie_clip.tracking.objects[0].tracks
            track = tracks.new(name="", frame=current_frame)
            track.markers[0].co = Vector((view_coord[0], view_coord[1]))
            track.lock = True
        
        return {'FINISHED'}
    

class IMAGE_OT_delete_2d_point(bpy.types.Operator):
    """Deletes point in clip editor corresponding to given global point coordinates"""

    bl_idname = "imagematches.delete_2d_point"
    bl_label = "Delete 2D point"
    # bl_options = {'REGISTER', 'UNDO'}

    point_x: bpy.props.FloatProperty(
        name='Mouse x', 
        description='Mouse x'
    )

    point_y: bpy.props.FloatProperty(
        name='Mouse y', 
        description='Mouse y'
    )

    def execute(self, context):
        """Delete point in clip editor"""

        # Deselect any currently active markers
        bpy.ops.clip.select_all(action='DESELECT')

        region = context.region
        # Coordinates within region are global coordinates - region location
        region_coord = self.point_x - region.x, self.point_y - region.y

        # Coordinates within image - 0 to 1 on each axis
        view_coord = region.view2d.region_to_view(region_coord[0], region_coord[1])

        # Only delete if within the bounds of the image so (0, 1)
        if 0 <= view_coord[0] <= 1 and 0 <= view_coord[1] <= 1:
            current_movie_clip = context.edit_movieclip

            for track in current_movie_clip.tracking.objects[0].tracks:
                marker = track.markers[0]
                marker_min_x = marker.co[0] + marker.pattern_bound_box[0][0]
                marker_max_x = marker.co[0] + marker.pattern_bound_box[1][0]
                marker_min_y = marker.co[1] + marker.pattern_bound_box[0][1]
                marker_max_y = marker.co[1] + marker.pattern_bound_box[1][1]

                if marker_min_x <= view_coord[0] <= marker_max_x and \
                    marker_min_y <= view_coord[1] <= marker_max_y:
                    track.select = True
                    # Couldn't see a simple way to delete a track directly,
                    # so use an ops call
                    bpy.ops.clip.delete_track(False)
                    break
        
        return {'FINISHED'}


class IMAGE_OT_add_points(bpy.types.Operator):
    """Add points in clip editor or 3D view"""

    bl_idname = "imagematches.add_points"
    bl_label = "Add points"
    # bl_options = {'REGISTER', 'UNDO'}
    window_clip = None
    area_clip = None
    region_clip = None
    window_3d = None
    area_3d = None
    region_3d = None

    def modal(self, context, event):
        settings = context.scene.match_settings
        
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            # allow navigation
            return {'PASS_THROUGH'}
        elif event.type == 'LEFTMOUSE' and event.value == "PRESS":
            # Only places points on mouse press, not release

            coord = event.mouse_x, event.mouse_y

            # If clicked within clip editor, then add marker
            if coordinates_within_region_bounds(self.region_clip, coord):
                with context.temp_override(window=self.window_clip, area=self.area_clip, region=self.region_clip):
                    bpy.ops.imagematches.add_2d_point('EXEC_DEFAULT', point_x=coord[0], point_y=coord[1])
            
            # If clicked within 3D view, then add point
            elif coordinates_within_region_bounds(self.region_3d, coord):
                with context.temp_override(window=self.window_3d, area=self.area_3d, region=self.region_3d):
                    bpy.ops.imagematches.add_3d_point('EXEC_DEFAULT', point_x=coord[0], point_y=coord[1])

            return {'RUNNING_MODAL'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            settings.add_points_enabled = False
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        settings = context.scene.match_settings

        # Find clip editor area
        self.window_clip, self.area_clip, self.region_clip = find_area(context, "CLIP_EDITOR")
        if self.area_clip is None: 
            self.report({'WARNING'}, "No clip editor open")
            settings.add_points_enabled = False
            return {'CANCELLED'}

        # Find 3D view area
        self.window_3d, self.area_3d, self.region_3d = find_area(context, "VIEW_3D")
        if self.area_3d is None: 
            self.report({'WARNING'}, "No 3D view open")
            settings.add_points_enabled = False
            return {'CANCELLED'}

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    

class IMAGE_OT_delete_points(bpy.types.Operator):
    """Delete points in clip editor or 3D view"""

    bl_idname = "imagematches.delete_points"
    bl_label = "Delete points"
    # bl_options = {'REGISTER', 'UNDO'}
    window_clip = None
    area_clip = None
    region_clip = None
    window_3d = None
    area_3d = None
    region_3d = None

    def modal(self, context, event):
        settings = context.scene.match_settings
        
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            # allow navigation
            return {'PASS_THROUGH'}
        elif event.type == 'LEFTMOUSE' and event.value == "PRESS":
            # Only places points on mouse press, not release

            coord = event.mouse_x, event.mouse_y

            # If clicked within clip editor, then add marker
            if coordinates_within_region_bounds(self.region_clip, coord):
                with context.temp_override(window=self.window_clip, area=self.area_clip, region=self.region_clip):
                    bpy.ops.imagematches.delete_2d_point('EXEC_DEFAULT', point_x=coord[0], point_y=coord[1])
            
            # If clicked within 3D view, then add point
            elif coordinates_within_region_bounds(self.region_3d, coord):
                with context.temp_override(window=self.window_3d, area=self.area_3d, region=self.region_3d):
                    bpy.ops.imagematches.delete_3d_point('EXEC_DEFAULT', point_x=coord[0], point_y=coord[1])

            return {'RUNNING_MODAL'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            settings.delete_points_enabled = False
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        settings = context.scene.match_settings

        # Find clip editor area
        self.window_clip, self.area_clip, self.region_clip = find_area(context, "CLIP_EDITOR")
        if self.area_clip is None: 
            self.report({'WARNING'}, "No clip editor open")
            settings.delete_points_enabled = False
            return {'CANCELLED'}

        # Find 3D view area
        self.window_3d, self.area_3d, self.region_3d = find_area(context, "VIEW_3D")
        if self.area_3d is None: 
            self.report({'WARNING'}, "No 3D view open")
            settings.delete_points_enabled = False
            return {'CANCELLED'}

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
        

def set_delete_points(self, context):
    if self.delete_points_enabled:
        bpy.ops.imagematches.delete_points('INVOKE_DEFAULT')


def set_add_points(self, context):
    if self.add_points_enabled:
        bpy.ops.imagematches.add_points('INVOKE_DEFAULT')
        

