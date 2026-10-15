import json
import math
import random
import mapbox_earcut
import numpy as np
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Vt

def parse_collage_json(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data.get("layers", [])

def perturb_polygon(polygon, max_displacement=0.1, segments_per_edge=5):
    """
    Subdivide edges and apply random displacement to simulate torn paper.
    """
    if len(polygon) < 3:
        return polygon

    new_polygon = []
    for i in range(len(polygon)):
        p1 = polygon[i]
        p2 = polygon[(i + 1) % len(polygon)]

        # Add the original point, possibly perturbed slightly
        new_polygon.append([
            p1[0] + (random.random() - 0.5) * max_displacement,
            p1[1] + (random.random() - 0.5) * max_displacement
        ])

        # Subdivide and perturb
        for j in range(1, segments_per_edge):
            t = j / segments_per_edge
            x = p1[0] * (1 - t) + p2[0] * t
            y = p1[1] * (1 - t) + p2[1] * t
            new_polygon.append([
                x + (random.random() - 0.5) * max_displacement,
                y + (random.random() - 0.5) * max_displacement
            ])

    return new_polygon

def generate_extruded_mesh_data(polygon, z_start, thickness):
    """
    Generate vertices, face vertex counts, and face vertex indices for an extruded polygon.
    """
    # Triangulate the 2D polygon for front and back faces
    verts = np.array(polygon, dtype=np.float32)
    # mapbox_earcut.triangulate_float32 takes a Nx2 array
    # returns an array of indices (flattened)
    ring_indices = np.array([len(polygon)], dtype=np.uint32)
    triangles = mapbox_earcut.triangulate_float32(verts, ring_indices).tolist()

    vertices = []
    num_pts = len(polygon)

    # Back face vertices (Z = z_start)
    for p in polygon:
        vertices.append((p[0], p[1], z_start))

    # Front face vertices (Z = z_start + thickness)
    for p in polygon:
        vertices.append((p[0], p[1], z_start + thickness))

    face_vertex_counts = []
    face_vertex_indices = []

    # Add back face triangles (winding reversed for back face)
    for i in range(0, len(triangles), 3):
        face_vertex_counts.append(3)
        face_vertex_indices.extend([triangles[i+2], triangles[i+1], triangles[i]])

    # Add front face triangles
    for i in range(0, len(triangles), 3):
        face_vertex_counts.append(3)
        face_vertex_indices.extend([triangles[i] + num_pts, triangles[i+1] + num_pts, triangles[i+2] + num_pts])

    # Add side faces (skirts) - quads
    for i in range(num_pts):
        next_i = (i + 1) % num_pts
        face_vertex_counts.append(4)
        # Quad connecting back and front
        face_vertex_indices.extend([
            i,              # back current
            next_i,         # back next
            next_i + num_pts, # front next
            i + num_pts       # front current
        ])

    return vertices, face_vertex_counts, face_vertex_indices

def create_pbr_material(stage, material_path, color, roughness):
    """
    Create a UsdPreviewSurface material.
    """
    material = UsdShade.Material.Define(stage, material_path)
    pbr_shader = UsdShade.Shader.Define(stage, material_path.AppendChild("PBRShader"))
    pbr_shader.CreateIdAttr("UsdPreviewSurface")

    pbr_shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)

    material.CreateSurfaceOutput().ConnectToSource(pbr_shader.ConnectableAPI(), "surface")
    return material

def export_collage_to_usd(layers, output_filepath):
    """
    Export layers to a USD stage.
    """
    stage = Usd.Stage.CreateNew(output_filepath)

    # Setup root and up-axis
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())

    collage = UsdGeom.Xform.Define(stage, "/World/Collage")

    layer_spacing = 1.0 # arbitrary spacing multiplier if needed, or just use absolute z_index

    for layer in layers:
        layer_id = layer["layer_id"]
        z_index = layer["z_index"]
        thickness = layer["thickness_mm"]
        color = layer.get("color", [0.8, 0.8, 0.8])
        roughness = layer.get("roughness", 0.9)
        polygon = layer["polygon"]

        # 1. Perturb polygon
        perturbed_polygon = perturb_polygon(polygon)

        # 2. Extrude
        z_start = z_index * layer_spacing
        vertices, face_counts, face_indices = generate_extruded_mesh_data(perturbed_polygon, z_start, thickness)

        # 3. Create USD structure
        layer_path = Sdf.Path(f"/World/Collage/{layer_id}")
        layer_xform = UsdGeom.Xform.Define(stage, layer_path)

        mesh_path = layer_path.AppendChild("Mesh")
        mesh = UsdGeom.Mesh.Define(stage, mesh_path)

        mesh.CreatePointsAttr(vertices)
        mesh.CreateFaceVertexCountsAttr(face_counts)
        mesh.CreateFaceVertexIndicesAttr(face_indices)

        # Subdiv scheme to none since we provide explicit faces
        mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)

        # Compute extents
        bounds = [(min([v[i] for v in vertices]), max([v[i] for v in vertices])) for i in range(3)]
        mesh.CreateExtentAttr([Gf.Vec3f(bounds[0][0], bounds[1][0], bounds[2][0]),
                               Gf.Vec3f(bounds[0][1], bounds[1][1], bounds[2][1])])

        # 4. Material Binding
        material_path = layer_path.AppendChild("Material")
        material = create_pbr_material(stage, material_path, color, roughness)

        UsdShade.MaterialBindingAPI(mesh).Bind(material)

    stage.GetRootLayer().Save()
    print(f"Successfully exported to {output_filepath}")


def test_extrusion():
    import tempfile
    import os

    # 1. Create a synthetic 3-layer polygon JSON specification
    synthetic_data = {
        "layers": [
            {
                "layer_id": "Layer_01",
                "z_index": 0,
                "thickness_mm": 0.5,
                "color": [0.8, 0.2, 0.2],
                "roughness": 0.9,
                "polygon": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
            },
            {
                "layer_id": "Layer_02",
                "z_index": 1,
                "thickness_mm": 0.3,
                "color": [0.2, 0.8, 0.2],
                "roughness": 0.8,
                "polygon": [[2.0, 2.0], [12.0, 2.0], [12.0, 8.0], [2.0, 8.0]]
            },
            {
                "layer_id": "Layer_03",
                "z_index": 2,
                "thickness_mm": 0.8,
                "color": [0.2, 0.2, 0.8],
                "roughness": 0.95,
                "polygon": [[4.0, 4.0], [8.0, 4.0], [6.0, 9.0]]
            }
        ]
    }

    # Save synthetic JSON to a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as json_file:
        json.dump(synthetic_data, json_file)
        json_path = json_file.name

    # 2. Call the exporter to produce a .usda file
    output_usda = "test_output.usda"
    if os.path.exists(output_usda):
        os.remove(output_usda)

    layers = parse_collage_json(json_path)
    export_collage_to_usd(layers, output_usda)

    # 3. Re-open the generated .usda file to verify the stage is valid
    assert os.path.exists(output_usda), "USD file was not generated"

    stage = Usd.Stage.Open(output_usda)
    assert stage is not None, "Failed to open the generated USD stage"

    # Verify hierarchy exists
    world_prim = stage.GetPrimAtPath("/World")
    assert world_prim.IsValid(), "/World prim is missing"

    collage_prim = stage.GetPrimAtPath("/World/Collage")
    assert collage_prim.IsValid(), "/World/Collage prim is missing"

    for layer in synthetic_data["layers"]:
        layer_id = layer["layer_id"]

        layer_path = f"/World/Collage/{layer_id}"
        layer_prim = stage.GetPrimAtPath(layer_path)
        assert layer_prim.IsValid(), f"Prim {layer_path} is missing"

        mesh_path = f"{layer_path}/Mesh"
        mesh_prim = stage.GetPrimAtPath(mesh_path)
        assert mesh_prim.IsValid(), f"Prim {mesh_path} is missing"
        assert mesh_prim.IsA(UsdGeom.Mesh), f"Prim {mesh_path} is not a UsdGeomMesh"

        material_path = f"{layer_path}/Material"
        material_prim = stage.GetPrimAtPath(material_path)
        assert material_prim.IsValid(), f"Prim {material_path} is missing"
        assert material_prim.IsA(UsdShade.Material), f"Prim {material_path} is not a UsdShadeMaterial"

        # Verify mesh properties
        mesh = UsdGeom.Mesh(mesh_prim)
        points_attr = mesh.GetPointsAttr().Get()
        assert points_attr is not None and len(points_attr) > 0, "Mesh points attribute is missing or empty"

        face_counts_attr = mesh.GetFaceVertexCountsAttr().Get()
        assert face_counts_attr is not None and len(face_counts_attr) > 0, "Mesh face vertex counts attribute is missing or empty"

        face_indices_attr = mesh.GetFaceVertexIndicesAttr().Get()
        assert face_indices_attr is not None and len(face_indices_attr) > 0, "Mesh face vertex indices attribute is missing or empty"

    print("All tests passed successfully!")

    # Cleanup
    os.remove(json_path)
    os.remove(output_usda)

if __name__ == "__main__":
    test_extrusion()
