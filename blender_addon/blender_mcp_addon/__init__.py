bl_info = {
    "name": "Blender MCP Server",
    "author": "Blender MCP",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Blender MCP",
    "description": "Exposes Blender to an MCP server over a local socket for AI-driven control and character design.",
    "category": "Interface",
}

import bpy
from . import server


class BLENDERMCP_OT_start(bpy.types.Operator):
    bl_idname = "blendermcp.start_server"
    bl_label = "Start MCP Server"
    bl_description = "Start the local socket server that the MCP bridge connects to"

    def execute(self, context):
        ok = server.start_server()
        self.report({"INFO"}, "MCP server started" if ok else "MCP server already running")
        return {"FINISHED"}


class BLENDERMCP_OT_stop(bpy.types.Operator):
    bl_idname = "blendermcp.stop_server"
    bl_label = "Stop MCP Server"
    bl_description = "Stop the local socket server"

    def execute(self, context):
        server.stop_server()
        self.report({"INFO"}, "MCP server stopped")
        return {"FINISHED"}


class BLENDERMCP_PT_panel(bpy.types.Panel):
    bl_label = "Blender MCP"
    bl_idname = "BLENDERMCP_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Blender MCP"

    def draw(self, context):
        layout = self.layout
        layout.operator("blendermcp.start_server", icon="PLAY")
        layout.operator("blendermcp.stop_server", icon="PAUSE")
        layout.label(text=f"Port: {server.PORT}")


classes = (BLENDERMCP_OT_start, BLENDERMCP_OT_stop, BLENDERMCP_PT_panel)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    # auto-start server on register
    try:
        server.start_server()
    except Exception:
        pass


def unregister():
    try:
        server.stop_server()
    except Exception:
        pass
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
