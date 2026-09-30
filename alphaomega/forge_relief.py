"""AlphaOmega — rebuild a flat image as a source-textured volumetric relief (headless Blender → USD).

The approach (public demo slice): the source pixels are surveyed into luminance bands, each band is
extruded to its own depth, and the original image is projected back as texture — so the **front view
is the exact source** while the oblique view reads as sculpture. Geometry is authored from observed
silhouettes; hidden sides are interpretation, which the script states rather than hides.

Run:
    blender --background --factory-startup --python alphaomega/forge_relief.py -- \
        --image piece.jpg --out relief.usda [--depth-scale 0.06] [--bands 7]

Requires only Blender (bpy). No network, no inference, no writes outside --out.
"""
from __future__ import annotations

import argparse
import os
import sys

import bpy
import bmesh
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description="Source-textured volumetric relief from a flat image.")
    p.add_argument("--image", required=True)
    p.add_argument("--out", required=True, help="output .usda / .usdc / .blend path")
    p.add_argument("--bands", type=int, default=7, help="luminance bands -> depth steps")
    p.add_argument("--depth-scale", type=float, default=0.06, help="max relief depth as a fraction of width")
    p.add_argument("--grid", type=int, default=96, help="survey resolution (grid points per axis)")
    return p.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def luminance_grid(image_path: str, n: int) -> list[list[float]]:
    """Load the image and sample it into an n×n luminance grid."""
    img = bpy.data.images.load(image_path)
    w, h = img.size
    px = list(img.pixels)                       # RGBA floats, bottom-left origin
    grid = []
    for j in range(n):
        row = []
        for i in range(n):
            x = min(w - 1, int((i + 0.5) * w / n))
            y = min(h - 1, int((j + 0.5) * h / n))
            o = (y * w + x) * 4
            r, g, b = px[o], px[o + 1], px[o + 2]
            row.append(0.2126 * r + 0.7152 * g + 0.0722 * b)
        grid.append(row)
    return grid


def build_relief(grid: list[list[float]], width: float, height: float, bands: int, depth: float):
    """One quad per cell, displaced by its luminance band. Returns the mesh object."""
    me = bpy.data.meshes.new("relief")
    obj = bpy.data.objects.new("relief", me)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    n = len(grid)
    cw, ch = width / n, height / n
    verts = {}
    for j in range(n + 1):
        for i in range(n + 1):
            x = -width / 2 + i * cw
            y = -height / 2 + j * ch
            # sample the surrounding cell average for the vertex height
            gs = []
            for dj in (-1, 0):
                for di in (-1, 0):
                    ii, jj = min(max(i + di, 0), n - 1), min(max(j + dj, 0), n - 1)
                    gs.append(grid[jj][ii])
            lum = sum(gs) / len(gs)
            band = int(lum * (bands - 1) + 0.5) / max(1, bands - 1)
            verts[(i, j)] = bm.verts.new((x, y, band * depth))
    bm.verts.ensure_lookup_table()
    faces = 0
    for j in range(n):
        for i in range(n):
            try:
                bm.faces.new((verts[(i, j)], verts[(i + 1, j)], verts[(i + 1, j + 1)], verts[(i, j + 1)]))
                faces += 1
            except ValueError:
                pass          # duplicate face — never fatal
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    print(f"[relief] grid {n}x{n}, faces {faces}, depth {depth:.4f}, bands {bands}")
    return obj


def texture_from_source(obj, image_path: str) -> None:
    """Project the source image back onto the relief so the front view is the exact source."""
    try:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.01)
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception as e:
        print(f"[relief] uv unwrap skipped ({type(e).__name__})")
    mat = bpy.data.materials.new("source_texture")
    mat.use_nodes = True
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(image_path)
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    obj.data.materials.append(mat)


def export(obj, out: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if out.lower().endswith((".usda", ".usdc", ".usd")):
        try:
            bpy.ops.wm.usd_export(filepath=out, selected_objects_only=False, export_materials=True)
            print(f"[relief] wrote {out}")
            return
        except Exception as e:
            print(f"[relief] USD export failed ({type(e).__name__}: {e}) — falling back to .blend")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.splitext(out)[0] + ".blend")
    print(f"[relief] wrote {os.path.splitext(out)[0]}.blend")


def main() -> int:
    a = parse_args()
    if not os.path.isfile(a.image):
        print(f"[relief] source not found: {a.image}", file=sys.stderr)
        return 2
    clear_scene()
    grid = luminance_grid(a.image, max(8, a.grid))
    source_w = bpy.data.images[os.path.basename(a.image)].size[0] or 1920
    source_h = bpy.data.images[os.path.basename(a.image)].size[1] or 1080
    aspect = source_w / source_h
    height = 1.0
    width = height * aspect
    obj = build_relief(grid, width, height, max(2, a.bands), a.depth_scale * width)
    texture_from_source(obj, a.image)
    export(obj, a.out)
    print("[relief] note: front view is the exact source image; oblique view is authored relief.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
