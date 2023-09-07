# image-matcher

Add-on for Blender that allows matching multiple 2D images to a corresponding 3D model. This uses OpenCV's Perspective-n-Point solver to estimate camera intrinsics (e.g. focal length, distortion coefficients) and extrinsics (camera position and orientation) based on pairs of 2D and 3D points.

This add-on builds on RT Studio's Camera Pnpoint Blender plugin: 
https://rtstudios.gumroad.com/l/camera_pnpoint / https://github.com/RT-studios/camera-pnpoint
Do consider buying their addon on gumroad/blender market to help support them making great Blender addons!

This plugin adds:
- Easier matching of multiple 2D images
- Point mode to allow one click addition of 2D/3D points
- UI to visualise list of points for each image
- Easier adjustment of camera parameters / background image directly in the plugin UI
- Export of camera parameters to JSON

For more information on the Perspective-n-Point process, see OpenCV's documentation: https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html