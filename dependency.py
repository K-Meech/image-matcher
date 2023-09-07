""" Based on original code from Robert Guetzkow
 https://github.com/robertguetzkow/blender-python-examples/tree/master/add_ons/install_dependencies
 https://blender.stackexchange.com/questions/168448/bundling-python-library-with-addon

 Based on molecular nodes package installation:
 https://github.com/BradyAJohnston/MolecularNodes/blob/main/MolecularNodes/pkg.py 
 """

import os
import sys
import subprocess
import importlib.util


def is_available(dependencies):
    """Check if all dependencies are available"""
    for dependency in dependencies:
        if importlib.util.find_spec(dependency.module) is None:
            return False

    return True


def run_python(cmd_list, timeout=600, check=False, env=None):
    """Runs pip command using the specified command list"""

    # path to python.exe
    python_exe = os.path.realpath(sys.executable)
    print(f"Using python at {python_exe}")

    # build the command list
    cmd_list = [python_exe] + cmd_list

    subprocess.run(
        cmd_list, timeout=timeout, check=check, env=env, stderr=subprocess.PIPE
    )


def install_all_dependencies(dependencies):
    """Install all dependencies using pip"""

    for dependency in dependencies:
        print(f"Installing {dependency.package}...")

        # Blender disables the loading of user site-packages by default.
        # However, pip will still check them to determine if a dependency is
        # already installed. This can cause problems if the packages is
        # installed in the user site-packages and pip deems the requirement
        # satisfied, but Blender cannot import the package from the user
        # site-packages. Hence, the environment variable PYTHONNOUSERSITE is
        # set to disallow pip from checking the user site-packages. If the
        # package is not already installed for Blender's Python interpreter,
        # it will then try to. The paths used by pip can be checked with
        # `subprocess.run([bpy.app.binary_path_python, "-m", "site"], check=True)`

        # Create a copy of the environment variables and modify them for
        # the subprocess call
        environ_copy = dict(os.environ)
        environ_copy["PYTHONNOUSERSITE"] = "1"

        run_python(
            ["-m", "pip", "install", dependency.package],
            check=True,
            env=environ_copy,
        )


def install_pip():
    """Installs pip if not already available"""
    print("Checking pip installation...")
    run_python(["-m", "ensurepip"])
