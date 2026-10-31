"""Example: build a complete stylized character using the blender-mcp bridge.

Prerequisite: Blender running with the Blender MCP addon (server up on 127.0.0.1:9876)
and `mcp_server` on sys.path.
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp_server"))
import blender_mcp as bm

bm.clear_scene()
bm.set_world_color(color=[0.15, 0.18, 0.25], strength=1.0)

# base humanoid
base = bm.create_character_base(name="Hero", height=2.0)
print("base:", base["result"]["parts"])

# materials
bm.skin_material_preset(name="Skin", tone="medium")
bm.fabric_material_preset(name="Shirt", color=[0.2, 0.35, 0.6])
bm.fabric_material_preset(name="Pants", color=[0.15, 0.15, 0.2])
bm.metal_material_preset(name="Buckle", color=[0.9, 0.85, 0.6])

# assign materials to parts
for part, mat in [("Hero_Head", "Skin"), ("Hero_Torso", "Shirt"),
                  ("Hero_ArmL", "Skin"), ("Hero_ArmR", "Skin"),
                  ("Hero_LegL", "Pants"), ("Hero_LegR", "Pants")]:
    bm.assign_material(object=part, material=mat)

# smoothing + symmetry
for p in ["Hero_Head", "Hero_Torso"]:
    bm.apply_subdivision(object=p, levels=2)
bm.apply_mirror(object="Hero_Torso", axis="X")

# facial blendshapes
bm.add_shape_key(object="Hero_Head", name="Smile")
bm.add_shape_key(object="Hero_Head", name="Blink")
bm.set_shape_key_value(object="Hero_Head", name="Smile", value=0.3)

# rig
bm.create_simple_rig(name="Hero", height=2.0)
bm.parent_object(child="Hero", parent="Hero_Rig", keep_transform=True)

# camera + lights + render
bm.create_camera(name="Cam", location=[4, -4, 3], rotation=[1.0, 0, 0.8])
bm.create_light(type="SUN", name="Key", location=[5, 5, 8], energy=4.0)
bm.create_light(type="AREA", name="Fill", location=[-3, -2, 2], energy=50.0)

out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "render", "hero.png"))
os.makedirs(os.path.dirname(out), exist_ok=True)
print(bm.render_image(filepath=out, resolution_x=512, resolution_y=512, samples=32, engine="CYCLES"))
print("rendered:", out)
