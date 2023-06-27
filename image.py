import bpy
import os


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