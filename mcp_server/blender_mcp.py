"""MCP server bridge to a running Blender instance.

Connects to the Blender addon's local socket (127.0.0.1:9876) and exposes
Blender operations as MCP tools, including helpers for character design.
"""

import json
import socket
import os
from typing import Any, Optional

from fastmcp import FastMCP

HOST = os.environ.get("BLENDER_HOST", "127.0.0.1")
PORT = int(os.environ.get("BLENDER_PORT", "9876"))

mcp = FastMCP("blender-mcp", instructions="Control Blender for 3D modeling and character design.")


def _send(command: str, params: dict = None, timeout: float = 120.0) -> dict:
    params = params or {}
    req = {"command": command, "params": params}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((HOST, PORT))
        sock.sendall((json.dumps(req) + "\n").encode("utf-8"))
        buf = b""
        while b"\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
        line = buf.split(b"\n", 1)[0].strip()
        if not line:
            raise RuntimeError("Empty response from Blender")
        resp = json.loads(line.decode("utf-8"))
    finally:
        sock.close()
    if resp.get("status") != "success":
        raise RuntimeError(resp.get("message", "Blender error") + ("\n" + resp.get("traceback", "") if resp.get("traceback") else ""))
    return resp.get("result")


# ---------- Core tools ----------

@mcp.tool
def ping() -> dict:
    """Check connection to Blender and return its version."""
    return _send("ping")


@mcp.tool
def get_scene_info() -> dict:
    """List all objects in the current Blender scene."""
    return _send("get_scene_info")


@mcp.tool
def get_object_info(name: str) -> dict:
    """Get detailed info (transforms, modifiers, materials, mesh stats) for an object."""
    return _send("get_object_info", {"name": name})


@mcp.tool
def create_primitive(
    type: str = "cube",
    name: Optional[str] = None,
    location: list = [0, 0, 0],
    rotation: list = [0, 0, 0],
    scale: Optional[list] = None,
    size: float = 2.0,
) -> dict:
    """Create a primitive mesh object. type: cube, sphere, ico_sphere, cylinder, cone, plane, torus, monkey."""
    params = {"type": type, "location": location, "rotation": rotation, "size": size}
    if name is not None:
        params["name"] = name
    if scale is not None:
        params["scale"] = scale
    return _send("create_primitive", params)


@mcp.tool
def delete_object(name: str) -> dict:
    """Delete an object by name."""
    return _send("delete_object", {"name": name})


@mcp.tool
def transform_object(
    name: str,
    location: Optional[list] = None,
    rotation: Optional[list] = None,
    scale: Optional[list] = None,
    new_name: Optional[str] = None,
) -> dict:
    """Move/rotate/scale/rename an object."""
    params = {"name": name}
    if location is not None:
        params["location"] = location
    if rotation is not None:
        params["rotation"] = rotation
    if scale is not None:
        params["scale"] = scale
    if new_name is not None:
        params["name_new"] = new_name
    return _send("transform_object", params)


@mcp.tool
def create_material(
    name: str = "Material",
    color: Optional[list] = None,
    metallic: float = 0.0,
    roughness: float = 0.5,
    emission: Optional[list] = None,
    emission_strength: float = 1.0,
) -> dict:
    """Create or update a Principled BSDF material. color is [r,g,b] or [r,g,b,a]."""
    params = {"name": name, "metallic": metallic, "roughness": roughness, "emission_strength": emission_strength}
    if color is not None:
        params["color"] = color
    if emission is not None:
        params["emission"] = emission
    return _send("create_material", params)


@mcp.tool
def assign_material(object: str, material: str) -> dict:
    """Assign a material to an object."""
    return _send("assign_material", {"object": object, "material": material})


@mcp.tool
def add_modifier(object: str, type: str, properties: Optional[dict] = None) -> dict:
    """Add a modifier to an object (e.g. SUBSURF, MIRROR, ARMATURE, SOLIDIFY, SMOOTH)."""
    params = {"object": object, "type": type}
    if properties:
        params["properties"] = properties
    return _send("add_modifier", params)


@mcp.tool
def create_armature(
    name: str = "Armature",
    location: list = [0, 0, 0],
    bones: Optional[list] = None,
) -> dict:
    """Create an armature. bones: list of {name, head, tail, parent}."""
    params = {"name": name, "location": location}
    if bones is not None:
        params["bones"] = bones
    return _send("create_armature", params)


@mcp.tool
def add_armature_modifier(object: str, armature: str, use_vertex_groups: bool = True) -> dict:
    """Bind a mesh to an armature via an Armature modifier."""
    return _send("add_armature_modifier", {"object": object, "armature": armature, "use_vertex_groups": use_vertex_groups})


@mcp.tool
def parent_object(child: str, parent: str, keep_transform: bool = True) -> dict:
    """Parent child object to parent (e.g. mesh to armature)."""
    return _send("parent_object", {"child": child, "parent": parent, "keep_transform": keep_transform})


@mcp.tool
def add_shape_key(object: str, name: str = "Key", value: float = 0.0) -> dict:
    """Add a shape key (blendshape) to a mesh."""
    return _send("add_shape_key", {"object": object, "name": name, "value": value})


@mcp.tool
def set_shape_key_value(object: str, name: str, value: float) -> dict:
    """Set a shape key's value (0..1 typically)."""
    return _send("set_shape_key_value", {"object": object, "name": name, "value": value})


@mcp.tool
def create_camera(name: Optional[str] = None, location: list = [5, -5, 5], rotation: list = [0.9, 0, 0.8]) -> dict:
    """Add a camera and set it as the active scene camera."""
    params = {"location": location, "rotation": rotation}
    if name is not None:
        params["name"] = name
    return _send("create_camera", params)


@mcp.tool
def create_light(type: str = "SUN", name: Optional[str] = None, location: list = [5, 5, 5], energy: float = 5.0, color: Optional[list] = None) -> dict:
    """Add a light (SUN, POINT, SPOT, AREA)."""
    params = {"type": type, "location": location, "energy": energy}
    if name is not None:
        params["name"] = name
    if color is not None:
        params["color"] = color
    return _send("create_light", params)


@mcp.tool
def render_image(
    filepath: str = "/tmp/render.png",
    resolution_x: int = 1024,
    resolution_y: int = 1024,
    samples: int = 64,
    engine: str = "CYCLES",
) -> dict:
    """Render the current scene to an image file."""
    return _send("render_image", {
        "filepath": filepath, "resolution_x": resolution_x, "resolution_y": resolution_y,
        "samples": samples, "engine": engine,
    })


@mcp.tool
def execute_blender_code(code: str) -> dict:
    """Execute arbitrary Python (bpy) code inside Blender. Use for advanced operations. The code runs in a namespace with bpy, math, bmesh available. Set a 'result' variable to return data."""
    return _send("execute_code", {"code": code}, timeout=300.0)


@mcp.tool
def clear_scene() -> dict:
    """Delete all objects in the scene."""
    return _send("clear_scene")


@mcp.tool
def set_world_color(color: list = [0.05, 0.05, 0.05], strength: float = 1.0) -> dict:
    """Set the world background color/strength."""
    return _send("set_world_color", {"color": color, "strength": strength})


# ---------- Character design helpers ----------

@mcp.tool
def create_character_base(
    name: str = "Character",
    height: float = 2.0,
) -> dict:
    """Create a simple humanoid base mesh from primitives (head, body, arms, legs) grouped under an empty. Good starting point for character design."""
    code = f'''
import bpy, math
name = {name!r}
height = {height}
# clear selection
bpy.ops.object.select_all(action="DESELECT")
parts = []
def make_prim(ptype, loc, scale, pname):
    if ptype == "cube":
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    elif ptype == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=loc)
    elif ptype == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1, location=loc)
    o = bpy.context.active_object
    o.scale = scale
    o.name = pname
    parts.append(o)
    return o

h = height
head_r = h * 0.12
make_prim("sphere", (0, 0, h*0.92), (head_r*2, head_r*2, head_r*2), name+"_Head")
make_prim("cube", (0, 0, h*0.55), (h*0.22, h*0.12, h*0.32), name+"_Torso")
make_prim("cylinder", (h*0.18, 0, h*0.55), (h*0.06, h*0.06, h*0.28), name+"_ArmL")
make_prim("cylinder", (-h*0.18, 0, h*0.55), (h*0.06, h*0.06, h*0.28), name+"_ArmR")
make_prim("cylinder", (h*0.07, 0, h*0.22), (h*0.07, h*0.07, h*0.22), name+"_LegL")
make_prim("cylinder", (-h*0.07, 0, h*0.22), (h*0.07, h*0.07, h*0.22), name+"_LegR")
# group under empty
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0,0,0))
root = bpy.context.active_object
root.name = name
for p in parts:
    p.parent = root
result = {{"root": root.name, "parts": [p.name for p in parts]}}
'''
    return _send("execute_code", {"code": code})


@mcp.tool
def create_simple_rig(name: str = "Character", height: float = 2.0) -> dict:
    """Create a basic humanoid armature (spine, head, arms, legs) suitable for character animation."""
    bones = [
        {"name": "Root", "head": [0, 0, 0], "tail": [0, 0, 0.1]},
        {"name": "Spine", "head": [0, 0, 0.1], "tail": [0, 0, height*0.55], "parent": "Root"},
        {"name": "Chest", "head": [0, 0, height*0.55], "tail": [0, 0, height*0.75], "parent": "Spine"},
        {"name": "Neck", "head": [0, 0, height*0.75], "tail": [0, 0, height*0.85], "parent": "Chest"},
        {"name": "Head", "head": [0, 0, height*0.85], "tail": [0, 0, height], "parent": "Neck"},
        {"name": "ArmL", "head": [0.1, 0, height*0.7], "tail": [height*0.35, 0, height*0.7], "parent": "Chest"},
        {"name": "ArmR", "head": [-0.1, 0, height*0.7], "tail": [-height*0.35, 0, height*0.7], "parent": "Chest"},
        {"name": "LegL", "head": [0.07, 0, height*0.5], "tail": [0.07, 0, 0.0], "parent": "Spine"},
        {"name": "LegR", "head": [-0.07, 0, height*0.5], "tail": [-0.07, 0, 0.0], "parent": "Spine"},
    ]
    return _send("create_armature", {"name": name + "_Rig", "location": [0, 0, 0], "bones": bones})


@mcp.tool
def apply_subdivision(object: str, levels: int = 2) -> dict:
    """Add a subdivision surface modifier (smooths character mesh)."""
    return _send("add_modifier", {"object": object, "type": "SUBSURF", "properties": {"levels": levels, "render_levels": levels}})


@mcp.tool
def apply_mirror(object: str, axis: str = "X") -> dict:
    """Add a mirror modifier along an axis (useful for symmetric characters)."""
    use_x = axis.upper() == "X"
    use_y = axis.upper() == "Y"
    use_z = axis.upper() == "Z"
    return _send("add_modifier", {"object": object, "type": "MIRROR", "properties": {
        "use_axis": (use_x, use_y, use_z),
    }})


@mcp.tool
def skin_material_preset(name: str = "Skin", tone: str = "medium") -> dict:
    """Create a skin-like material. tone: light, medium, dark, fantasy."""
    tones = {
        "light": [0.95, 0.82, 0.72],
        "medium": [0.78, 0.58, 0.42],
        "dark": [0.45, 0.30, 0.22],
        "fantasy": [0.6, 0.85, 0.7],
    }
    c = tones.get(tone, tones["medium"])
    return _send("create_material", {"name": name, "color": c + [1.0], "metallic": 0.0, "roughness": 0.6})


@mcp.tool
def fabric_material_preset(name: str = "Fabric", color: list = [0.2, 0.3, 0.6]) -> dict:
    """Create a fabric/cloth material."""
    return _send("create_material", {"name": name, "color": color + ([1.0] if len(color) == 3 else []), "metallic": 0.0, "roughness": 0.9})


@mcp.tool
def metal_material_preset(name: str = "Metal", color: list = [0.8, 0.8, 0.85]) -> dict:
    """Create a metal material."""
    return _send("create_material", {"name": name, "color": color + ([1.0] if len(color) == 3 else []), "metallic": 1.0, "roughness": 0.25})


@mcp.tool
def cartoon_material_preset(name: str = "Cartoon", color: list = [0.9, 0.4, 0.2]) -> dict:
    """Create a flat/cartoonish material (low roughness, bright)."""
    return _send("create_material", {"name": name, "color": color + ([1.0] if len(color) == 3 else []), "metallic": 0.0, "roughness": 0.4})


@mcp.tool
def get_viewport_screenshot(filepath: str = "C:/temp/blender_viewport.png") -> dict:
    """Render an OpenGL viewport screenshot to a file."""
    return _send("get_viewport_screenshot", {"filepath": filepath})


if __name__ == "__main__":
    mcp.run()
