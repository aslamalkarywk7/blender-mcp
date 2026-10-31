"""Socket server that runs inside Blender and executes commands on the main thread.

Protocol (newline-delimited JSON over TCP, default 127.0.0.1:9876):

Request:  {"command": "<name>", "params": {...}, "request_id": "<id>"}
Response: {"status": "success"|"error", "result": ..., "message": "...", "request_id": "<id>"}
"""

import json
import socket
import threading
import queue
import traceback

HOST = "127.0.0.1"
PORT = 9876

_command_queue = queue.Queue()
_server_thread = None
_server_socket = None
_running = False
_timer_registered = False


def _safe_exec(code, namespace=None):
    if namespace is None:
        namespace = {}
    import bpy
    namespace.setdefault("bpy", bpy)
    namespace.setdefault("math", __import__("math"))
    namespace.setdefault("bmesh", __import__("bmesh"))
    exec(compile(code, "<blender_mcp>", "exec"), namespace)
    return namespace


def handle_command(cmd):
    """Execute a single command dict and return a result value (or raise)."""
    import bpy

    command = cmd.get("command")
    params = cmd.get("params") or {}

    if command == "ping":
        return {"pong": True, "blender_version": list(bpy.app.version)}

    if command == "get_scene_info":
        scene = bpy.context.scene
        objects = []
        for obj in scene.objects:
            objects.append({
                "name": obj.name,
                "type": obj.type,
                "location": [round(x, 4) for x in obj.location],
                "rotation_euler": [round(x, 4) for x in obj.rotation_euler],
                "scale": [round(x, 4) for x in obj.scale],
                "visible": not obj.hide_viewport,
            })
        return {
            "scene_name": scene.name,
            "frame_current": scene.frame_current,
            "render_engine": scene.render.engine,
            "object_count": len(objects),
            "objects": objects,
        }

    if command == "get_object_info":
        name = params["name"]
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise ValueError(f"Object not found: {name}")
        info = {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation_euler": list(obj.rotation_euler),
            "scale": list(obj.scale),
            "modifiers": [m.type for m in obj.modifiers],
            "material_slots": [s.material.name if s.material else None for s in obj.material_slots],
        }
        if obj.type == "MESH" and obj.data is not None:
            mesh = obj.data
            info["vertices"] = len(mesh.vertices)
            info["edges"] = len(mesh.edges)
            info["faces"] = len(mesh.polygons)
            info["shape_keys"] = [k.name for k in mesh.shape_keys.key_blocks] if mesh.shape_keys else []
        if obj.type == "ARMATURE":
            info["bones"] = [b.name for b in obj.data.bones]
        return info

    if command == "create_primitive":
        ptype = params.get("type", "cube").lower()
        name = params.get("name")
        location = params.get("location", [0, 0, 0])
        rotation = params.get("rotation", [0, 0, 0])
        scale = params.get("scale")
        size = params.get("size", 2.0)
        ops = {
            "cube": bpy.ops.mesh.primitive_cube_add,
            "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
            "ico_sphere": bpy.ops.mesh.primitive_ico_sphere_add,
            "cylinder": bpy.ops.mesh.primitive_cylinder_add,
            "cone": bpy.ops.mesh.primitive_cone_add,
            "plane": bpy.ops.mesh.primitive_plane_add,
            "torus": bpy.ops.mesh.primitive_torus_add,
            "monkey": bpy.ops.mesh.primitive_monkey_add,
        }
        if ptype not in ops:
            raise ValueError(f"Unknown primitive type: {ptype}")
        kw = {"location": tuple(location), "rotation": tuple(rotation)}
        if ptype in ("cube",):
            kw["size"] = size
        if ptype in ("sphere", "ico_sphere"):
            kw["radius"] = size / 2.0
        if ptype == "cylinder":
            kw["radius"] = size / 2.0
            kw["depth"] = size
        if ptype == "cone":
            kw["radius1"] = size / 2.0
            kw["depth"] = size
        if ptype == "plane":
            kw["size"] = size
        if ptype == "torus":
            kw["major_radius"] = size / 2.0
            kw["minor_radius"] = size / 8.0
        ops[ptype](**kw)
        obj = bpy.context.active_object
        if name:
            obj.name = name
        if scale:
            obj.scale = tuple(scale)
        return {"name": obj.name, "type": obj.type}

    if command == "delete_object":
        name = params["name"]
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise ValueError(f"Object not found: {name}")
        bpy.data.objects.remove(obj, do_unlink=True)
        return {"deleted": name}

    if command == "transform_object":
        name = params["name"]
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise ValueError(f"Object not found: {name}")
        if "location" in params:
            obj.location = tuple(params["location"])
        if "rotation" in params:
            obj.rotation_euler = tuple(params["rotation"])
        if "scale" in params:
            obj.scale = tuple(params["scale"])
        if "name_new" in params:
            obj.name = params["name_new"]
        return {"name": obj.name}

    if command == "create_material":
        mat_name = params.get("name", "Material")
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            if "color" in params:
                c = params["color"]
                if len(c) == 3:
                    c = c + [1.0]
                bsdf.inputs["Base Color"].default_value = tuple(c)
            if "metallic" in params:
                bsdf.inputs["Metallic"].default_value = float(params["metallic"])
            if "roughness" in params:
                bsdf.inputs["Roughness"].default_value = float(params["roughness"])
            if "emission" in params:
                e = params["emission"]
                if len(e) == 3:
                    e = e + [1.0]
                bsdf.inputs["Emission Color"].default_value = tuple(e)
                bsdf.inputs["Emission Strength"].default_value = float(params.get("emission_strength", 1.0))
        return {"name": mat.name}

    if command == "assign_material":
        obj_name = params["object"]
        mat_name = params["material"]
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            raise ValueError(f"Object not found: {obj_name}")
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            raise ValueError(f"Material not found: {mat_name}")
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
        return {"object": obj.name, "material": mat.name}

    if command == "add_modifier":
        obj_name = params["object"]
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            raise ValueError(f"Object not found: {obj_name}")
        mtype = params["type"]
        mod = obj.modifiers.new(name=mtype, type=mtype)
        for k, v in (params.get("properties") or {}).items():
            try:
                setattr(mod, k, v)
            except Exception:
                pass
        return {"object": obj.name, "modifier": mod.name, "type": mod.type}

    if command == "create_armature":
        name = params.get("name", "Armature")
        arm_data = bpy.data.armatures.new(name + "_data")
        obj = bpy.data.objects.new(name, arm_data)
        bpy.context.collection.objects.link(obj)
        loc = params.get("location", [0, 0, 0])
        obj.location = tuple(loc)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        # add bones via edit mode
        bones = params.get("bones", [])
        bpy.ops.object.mode_set(mode="EDIT")
        for b in bones:
            eb = arm_data.edit_bones.new(b["name"])
            eb.head = tuple(b.get("head", [0, 0, 0]))
            eb.tail = tuple(b.get("tail", [0, 1, 0]))
            if "parent" in b:
                eb.parent = arm_data.edit_bones.get(b["parent"])
        bpy.ops.object.mode_set(mode="OBJECT")
        return {"name": obj.name, "bones": [bn.name for bn in obj.data.bones]}

    if command == "add_armature_modifier":
        obj_name = params["object"]
        arm_name = params["armature"]
        obj = bpy.data.objects.get(obj_name)
        arm = bpy.data.objects.get(arm_name)
        if obj is None or arm is None:
            raise ValueError("Object or armature not found")
        mod = obj.modifiers.new(name="Armature", type="ARMATURE")
        mod.object = arm
        if params.get("use_vertex_groups", True):
            mod.use_vertex_groups = True
        return {"object": obj.name, "modifier": mod.name, "armature": arm.name}

    if command == "parent_object":
        child = bpy.data.objects.get(params["child"])
        parent = bpy.data.objects.get(params["parent"])
        if child is None or parent is None:
            raise ValueError("Child or parent not found")
        child.parent = parent
        if params.get("keep_transform", True):
            child.matrix_parent_inverse = parent.matrix_world.inverted()
        return {"child": child.name, "parent": parent.name}

    if command == "add_shape_key":
        obj_name = params["object"]
        obj = bpy.data.objects.get(obj_name)
        if obj is None or obj.type != "MESH":
            raise ValueError("Mesh object not found")
        if obj.data.shape_keys is None:
            obj.shape_key_add(name="Basis")
        sk = obj.shape_key_add(name=params.get("name", "Key"))
        if "value" in params:
            sk.value = float(params["value"])
        return {"object": obj.name, "shape_key": sk.name}

    if command == "set_shape_key_value":
        obj_name = params["object"]
        obj = bpy.data.objects.get(obj_name)
        if obj is None or obj.data.shape_keys is None:
            raise ValueError("No shape keys")
        kb = obj.data.shape_keys.key_blocks.get(params["name"])
        if kb is None:
            raise ValueError(f"Shape key not found: {params['name']}")
        kb.value = float(params["value"])
        return {"object": obj.name, "shape_key": kb.name, "value": kb.value}

    if command == "create_camera":
        loc = params.get("location", [5, -5, 5])
        rot = params.get("rotation", [0.9, 0, 0.8])
        bpy.ops.object.camera_add(location=tuple(loc), rotation=tuple(rot))
        cam = bpy.context.active_object
        if "name" in params:
            cam.name = params["name"]
        bpy.context.scene.camera = cam
        return {"name": cam.name}

    if command == "create_light":
        ltype = params.get("type", "SUN").upper()
        loc = params.get("location", [5, 5, 5])
        bpy.ops.object.light_add(type=ltype, location=tuple(loc))
        light = bpy.context.active_object
        if "name" in params:
            light.name = params["name"]
        if "energy" in params:
            light.data.energy = float(params["energy"])
        if "color" in params:
            c = params["color"]
            if len(c) == 3:
                c = c + [1.0]
            light.data.color = tuple(c[:3])
        return {"name": light.name, "type": ltype}

    if command == "render_image":
        scene = bpy.context.scene
        if scene.camera is None:
            bpy.ops.object.camera_add(location=(5, -5, 5), rotation=(0.9, 0, 0.8))
            scene.camera = bpy.context.active_object
        if "filepath" in params:
            scene.render.filepath = params["filepath"]
        if "resolution_x" in params:
            scene.render.resolution_x = int(params["resolution_x"])
        if "resolution_y" in params:
            scene.render.resolution_y = int(params["resolution_y"])
        if "samples" in params:
            try:
                scene.cycles.samples = int(params["samples"])
            except Exception:
                pass
        if "engine" in params:
            scene.render.engine = params["engine"]
        bpy.ops.render.render(write_still=True)
        return {"filepath": scene.render.filepath}

    if command == "get_viewport_screenshot":
        path = params.get("filepath", "/tmp/blender_viewport.png")
        bpy.context.scene.render.filepath = path
        try:
            bpy.ops.render.opengl(write_still=True)
        except Exception:
            # Fallback for headless / no GL context
            if bpy.context.scene.camera is None and bpy.data.objects.get("Camera") is not None:
                bpy.context.scene.camera = bpy.data.objects["Camera"]
            bpy.ops.render.render(write_still=True)
        return {"filepath": path}

    if command == "execute_code":
        code = params["code"]
        result = _safe_exec(code)
        # try to extract a 'result' variable
        out = result.get("result", None)
        # convert non-serializable
        try:
            json.dumps(out)
        except Exception:
            out = str(out)
        return {"executed": True, "result": out}

    if command == "clear_scene":
        # delete all objects
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        return {"cleared": True}

    if command == "set_world_color":
        world = bpy.context.scene.world
        if world is None:
            world = bpy.data.worlds.new("World")
            bpy.context.scene.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
        if bg:
            c = params.get("color", [0.05, 0.05, 0.05, 1.0])
            if len(c) == 3:
                c = c + [1.0]
            bg.inputs[0].default_value = tuple(c)
            bg.inputs[1].default_value = float(params.get("strength", 1.0))
        return {"world": world.name}

    raise ValueError(f"Unknown command: {command}")


def _process_queue():
    """Timer callback running on Blender's main thread."""
    global _running
    try:
        while True:
            try:
                item = _command_queue.get_nowait()
            except queue.Empty:
                break
            req, event, container = item
            try:
                result = handle_command(req)
                container["response"] = {"status": "success", "result": result, "request_id": req.get("request_id")}
            except Exception as e:
                container["response"] = {"status": "error", "message": str(e), "traceback": traceback.format_exc(), "request_id": req.get("request_id")}
            event.set()
    except Exception:
        pass
    return 0.05 if _running else None


def _server_loop():
    global _server_socket, _running
    _server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _server_socket.bind((HOST, PORT))
    _server_socket.listen(8)
    _server_socket.settimeout(1.0)
    while _running:
        try:
            conn, addr = _server_socket.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        threading.Thread(target=_handle_connection, args=(conn,), daemon=True).start()


def _handle_connection(conn):
    global _running
    buf = b""
    try:
        conn.settimeout(30.0)
        while _running:
            data = conn.recv(65536)
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    req = json.loads(line.decode("utf-8"))
                except Exception as e:
                    resp = {"status": "error", "message": f"Invalid JSON: {e}"}
                    conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                    continue
                event = threading.Event()
                container = {}
                _command_queue.put((req, event, container))
                if not event.wait(timeout=120.0):
                    resp = {"status": "error", "message": "Timeout waiting for Blender main thread"}
                else:
                    resp = container.get("response", {"status": "error", "message": "No response"})
                conn.sendall((json.dumps(resp, default=str) + "\n").encode("utf-8"))
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def start_server():
    global _server_thread, _running, _timer_registered
    if _running:
        return False
    _running = True
    _server_thread = threading.Thread(target=_server_loop, daemon=True)
    _server_thread.start()
    import bpy
    if not bpy.app.timers.is_registered(_process_queue):
        bpy.app.timers.register(_process_queue, persistent=True)
        _timer_registered = True
    return True


def stop_server():
    global _server_socket, _running, _timer_registered
    _running = False
    if _server_socket is not None:
        try:
            _server_socket.close()
        except Exception:
            pass
        _server_socket = None
    import bpy
    if _timer_registered and bpy.app.timers.is_registered(_process_queue):
        bpy.app.timers.unregister(_process_queue)
        _timer_registered = False
    return True
