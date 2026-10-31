# Blender MCP Server

Control **Blender** from an AI agent (OpenCode, Claude Desktop, Cursor, etc.) over the
[Model Context Protocol (MCP)](https://modelcontextprotocol.io), and use it to design 3D
characters. The project has two parts:

1. **Blender addon** (`blender_addon/blender_mcp_addon`) — runs inside Blender, exposes a
   local TCP socket (default `127.0.0.1:9876`) that executes `bpy` commands on Blender's
   main thread.
2. **MCP server** (`mcp_server/blender_mcp.py`) — a FastMCP (stdio) server that connects
   to the Blender socket and exposes 28 tools, including high-level character-design
   helpers (base mesh, rig, materials, shape keys, rendering).

## Requirements

- Blender 4.x or 5.x (tested on 5.2.3)
- Python 3.10+ on the host (for the MCP server)
- `fastmcp` (installed automatically below)

## Install

### 1. Install the Blender addon

Option A — copy the folder:

```
# Windows
copy /s blender_addon\blender_mcp_addon "%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\blender_mcp_addon"
```

Option B — install from zip: zip the `blender_addon/blender_mcp_addon` folder and use
*Edit → Preferences → Add-ons → Install*.

Then enable **Blender MCP Server** in the add-ons list. The socket server auto-starts on
addon load (port 9876). A panel is available in the 3D Viewport sidebar (N) under
"Blender MCP" with Start/Stop buttons.

### 2. Install the MCP server

```bash
cd mcp_server
pip install -r requirements.txt
```

`requirements.txt`:
```
fastmcp>=2.0
```

### 3. Register the MCP server with your client

**OpenCode** (`~/.config/opencode/opencode.json` or project `opencode.json`):

```json
{
  "mcp": {
    "blender": {
      "type": "local",
      "command": ["python", "C:/path/to/blender-mcp/mcp_server/blender_mcp.py"],
      "enabled": true
    }
  }
}
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "blender": {
      "command": "python",
      "args": ["C:/path/to/blender-mcp/mcp_server/blender_mcp.py"]
    }
  }
}
```

Environment overrides: `BLENDER_HOST`, `BLENDER_PORT`.

## Usage

1. Open Blender (GUI). The addon's server starts automatically.
2. Start your AI client with the MCP server configured.
3. Ask the agent to design a character, e.g.:

> "Create a stylized character named 'Hero', 2 units tall, with skin and cloth
>  materials, a mirror modifier, a subdivision surface, and a basic rig. Render a
>  front view to C:/renders/hero.png."

The agent will call `clear_scene`, `create_character_base`, `skin_material_preset`,
`fabric_material_preset`, `apply_mirror`, `apply_subdivision`, `create_simple_rig`,
`create_camera`, `create_light`, `render_image`.

## Tools

Core: `ping`, `get_scene_info`, `get_object_info`, `create_primitive`,
`delete_object`, `transform_object`, `create_material`, `assign_material`,
`add_modifier`, `create_armature`, `parent_object`, `add_shape_key`,
`set_shape_key_value`, `create_camera`, `create_light`, `render_image`,
`execute_blender_code`, `clear_scene`, `set_world_color`,
`get_viewport_screenshot`.

Character helpers: `create_character_base`, `create_simple_rig`,
`apply_subdivision`, `apply_mirror`, `skin_material_preset`,
`fabric_material_preset`, `metal_material_preset`, `cartoon_material_preset`.

`execute_blender_code` runs arbitrary `bpy` Python inside Blender (escape hatch for
anything not covered by a dedicated tool). Set a `result` variable to return data.

## Character design workflow

1. `clear_scene`
2. `create_character_base(name, height)` — builds head/torso/arms/legs under an empty.
3. `skin_material_preset` + `fabric_material_preset` + assign to parts.
4. `apply_mirror(object=torso)` for symmetry, `apply_subdivision` for smoothness.
5. `create_simple_rig` + `parent_object` (mesh → armature) for animation.
6. `add_shape_key` for facial expressions (smile, blink, ...).
7. `create_camera`, `create_light`, `render_image`.

## Running without a GPU (RDP / headless machines)

If Blender complains about **OpenGL 4.3** (common on Remote Desktop / old GPUs),
use the headless runner instead of the GUI:

```bat
cd "C:\Users\RDP\Documents\Default Project\blender-mcp"
start_blender.bat
```

This runs Blender in `--background` mode with a manual command queue pump, so no
OpenGL context is needed. All MCP tools keep working and rendering uses Cycles on
CPU. The socket server starts on `127.0.0.1:9876` as usual.

Alternatively, install a software OpenGL driver (Mesa3D) to enable the full GUI.

## Notes / limitations

- Blender's `bpy` is not thread-safe; the addon queues commands and runs them on
  Blender's main thread via `bpy.app.timers`, so keep Blender's UI responsive.
- Rendering uses whatever engine you select; Cycles on CPU is safest in headless
  environments. EEVEE may require a GPU/display.
- The socket binds to localhost only.
- Large scenes / long renders: the bridge waits up to 120s (execute_code up to 300s).

## License

MIT
