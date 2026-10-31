@echo off
cd /d "C:\Users\RDP\Documents\Default Project\blender-mcp"
echo Starting Blender (headless) with MCP server...
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python run_blender_headless.py
pause
