# GNV Relief Extrusion Specification

## Overview
The GNV Relief Extruder converts 2D segmentation masks (derived from SAM 2 or Roboflow) into 3D OpenUSD stages. It treats analogue collages as physical relief constructions by extruding 2D polygons along the Z-axis, simulating paper thickness, and applying edge perturbations to simulate torn paper edges.

## Input JSON Schema
The extruder ingests a JSON file describing a multi-layer collage. The JSON should be an array of layer objects or an object containing a list of layers.

### JSON Structure
```json
{
  "layers": [
    {
      "layer_id": "Layer_01",
      "z_index": 0,
      "thickness_mm": 0.5,
      "color": [0.8, 0.8, 0.8],
      "roughness": 0.9,
      "polygon": [
        [0.0, 0.0],
        [10.0, 0.0],
        [10.0, 10.0],
        [0.0, 10.0]
      ]
    }
  ]
}
```

### Fields
- `layer_id` (string): Unique identifier for the layer. Determines the node name in the USD hierarchy.
- `z_index` (integer): Relative layer depth index (Z=0..N). Used to offset the layer along the Z-axis.
- `thickness_mm` (float): Extruded paper thickness in millimeters (typically 0.2mm - 0.8mm).
- `color` (array of floats): RGB diffuse color for the layer material.
- `roughness` (float): Roughness value for the PBR material.
- `polygon` (array of array of floats): Ordered list of [X, Y] vertices defining the 2D contour of the segment.

## 3D Generation Process

1. **Parsing**: The JSON specification is read and each layer is parsed.
2. **Edge Perturbation**: The 2D polygon vertices are linearly interpolated to ensure sufficient density, then a noise or random displacement function is applied to the boundary coordinates to simulate the rough, fibrous tearing of physical paper.
3. **Extrusion**: The perturbed 2D polygon is triangulated to form a front face and a back face. The front face is placed at `Z = z_index * (layer_spacing) + thickness_mm` and the back face at `Z = z_index * (layer_spacing)`. A side surface (skirt) connects the front and back boundaries.
4. **USD Mesh Construction**: A `UsdGeomMesh` is constructed using the generated 3D vertices, face vertex counts, and face vertex indices.
5. **PBR Material Binding**: A `UsdPreviewSurface` material is created for each layer, configuring the diffuse color and roughness. The material is then bound to the corresponding `UsdGeomMesh`.

## Target OpenUSD Hierarchy
The output is a valid `.usda` or `.usdc` file containing the following scene graph structure:

```
/World
  /Collage
    /Layer_01
      /Mesh
      /Material
    /Layer_02
      /Mesh
      /Material
    ...
```

- `/World`: The default root primitive.
- `/World/Collage`: The container for all collage layers.
- `/World/Collage/Layer_NN`: An Xform or Scope for a specific layer.
- `/World/Collage/Layer_NN/Mesh`: The `UsdGeomMesh` representing the extruded paper.
- `/World/Collage/Layer_NN/Material`: The `UsdPreviewSurface` material and shading network bound to the mesh.
