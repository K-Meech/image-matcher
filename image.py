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


def ray_cast(context, event):
    """Run this function on left mouse, execute the ray cast"""
    # get the context arguments
    print("ray cast go....")
    scene = context.scene
    region = context.region
    rv3d = context.region_data
    coord = event.mouse_region_x, event.mouse_region_y
    settings = context.scene.match_settings

    # get the ray from the viewport and mouse
    view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)

    ray_target = ray_origin + view_vector

    # cast rays and find the closest object
    best_length_squared = -1.0
    best_obj = None
    best_hit = None

    # Here the cursor is set to the location of the hit - could use this
    # to spawn empty??
    for obj, matrix in visible_objects_and_duplis(context):
        if obj.type == 'MESH':
            hit, normal, face_index = obj_ray_cast(ray_origin, ray_target, obj, matrix)
            if hit is not None:
                hit_world = matrix @ hit
                scene.cursor.location = hit_world
                length_squared = (hit_world - ray_origin).length_squared
                if best_hit is None or length_squared < best_length_squared:
                    best_length_squared = length_squared
                    best_obj = obj
                    best_hit = hit_world

    if best_hit is not None:
        empty = bpy.data.objects.new("empty", None)
        empty.empty_display_type = "SPHERE"
        empty.empty_display_size = 0.1
        empty.location = best_hit
        
        image_collection = settings.current_image_collection
        point_collection = image_collection.children[settings.points_collection_name]
        point_collection.objects.link(empty)

    # # now we have the object under the mouse cursor,
    # # we could do lots of stuff but for the example just select.
    # if best_obj is not None:
    #     # for selection etc. we need the original object,
    #     # evaluated objects are not in viewlayer
    #     best_original = best_obj.original

    #     print("Changing properties...")
    #     best_original.material_slots[0].material.diffuse_color=(1, 0, 0, 0.8)

    #     best_original.select_set(True)
    #     context.view_layer.objects.active = best_original


def add_clip_marker(context, event):
    scene = context.scene
    region = context.region
    rv3d = context.region_data
    region_coord = event.mouse_region_x, event.mouse_region_y
    view_coord = region.view2d.region_to_view(region_coord[0], region_coord[1])
    settings = context.scene.match_settings
    print(f"coords: {view_coord[0]}, {view_coord[1]}")

    # Only add markers if lie within the bounds of the image so (0, 1)
    if view_coord[0] >= 0 and view_coord[0] <= 1 and view_coord[1] >= 0 and view_coord[1] <= 1:
        current_movie_clip = context.edit_movieclip
        current_frame = context.scene.frame_current
        

        # track = current_movie_clip.tracking.tracks.new(name="")
        track = current_movie_clip.tracking.tracks.new(name="", frame=current_frame)
        track.markers[0].co = Vector((view_coord[0], view_coord[1]))
        # track.markers.insert_frame(current_frame, co=(view_coord[0], view_coord[1]))
        # bpy.ops.clip.add_marker(location=view_coord)


# Can check for currently active handlers with 
# bpy.context.window_manager.operators.keys() in blender terminal??
class IMAGE_OT_add_points(bpy.types.Operator):
    """Add points"""
    bl_idname = "imagematches.add_points"
    bl_label = "Add points"
    # bl_options = {'REGISTER', 'UNDO'}

    def modal(self, context, event):
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            # allow navigation
            return {'PASS_THROUGH'}
        elif event.type == 'LEFTMOUSE':
            if context.space_data.type == "VIEW_3D":
                ray_cast(context, event)
            else:
                add_clip_marker(context, event)
            return {'RUNNING_MODAL'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.space_data.type == 'VIEW_3D' or context.space_data.type == "CLIP_EDITOR":
            print("adding modal handler")
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be View3d or Clip Editor")
            return {'CANCELLED'}

