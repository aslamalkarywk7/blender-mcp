"""Run Blender in headless (no-GUI) mode with the MCP socket server active.

Use this on machines without an OpenGL 4.3-capable GPU (e.g. RDP sessions).
All MCP tools work; rendering uses Cycles on CPU.

Usage:
    blender.exe --background --python run_blender_headless.py
"""
import bpy
import addon_utils
import time
import sys
import os

# Enable the installed addon
try:
    addon_utils.enable("blender_mcp_addon", default_set=True)
except Exception as e:
    print("addon enable:", e, flush=True)

# Import server module
try:
    import blender_mcp_addon.server as srv
except Exception:
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "blender_addon"))
    import blender_mcp_addon.server as srv

print("Blender MCP server starting on %s:%d" % (srv.HOST, srv.PORT), flush=True)
if not srv._running:
    srv.start_server()

print("Blender MCP server UP (headless). Ctrl+C to stop.", flush=True)

# Background mode exits after the script; keep alive by pumping the queue manually.
while True:
    try:
        srv._process_queue()
    except Exception as e:
        print("pump error:", e, flush=True)
    time.sleep(0.05)
