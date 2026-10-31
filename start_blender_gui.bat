@echo off
set GALLIUM_DRIVER=llvmpipe
set LIBGL_ALWAYS_SOFTWARE=1
echo Starting Blender (GUI) with Mesa software OpenGL...
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
pause
