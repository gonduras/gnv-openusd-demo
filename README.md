# GNV — OpenUSD Genealogy for Analogue Collage (public demo)

**This is the public demonstration slice of the GMM / GONDURASTRATION system** submitted to the
**Nebius × NVIDIA Global AI Hackathon** (track: *Coding and agentic engineering*).

> The artist's vault — the artwork library, trained checkpoints and lineage records — is **private**.
> Nothing in this repository contains artworks, model weights or credentials. It contains the
> *schema, the agent layer and the reconstruction approach* so the design can be read and run.

---

## The problem this answers
Analogue collage has no machine-readable language. Generative stacks read *prompts*, not *paper*:
ink density, newsprint grain, tape residue, resin sheen, torn-edge step discontinuities. An artist
with two decades of physical work cannot ask a model **"is this actually my style?"** — and nothing
records where a neural render came from.

## The six canonical axes
Every image is scored 0.00–1.00 on six axes (`six_axes/axes.py`):

| Axis | Reads |
|---|---|
| `Material_Substrate` | litho ink density, newsprint grain, tape residue, resin sheen |
| `Exposure_Fracture` | scorched Mediterranean light, directional shadow cuts |
| `Structural_Glitch` | anti-retinal disruption, substrate tears, transparent epoxy borders |
| `Graphic_Vector` | diagonal spatial geometry, high-density vector composition |
| `Zero_Plane` | non-objective zero-degree field, floating primitives — **< 0.40 is a hard reject** |
| `Faceted_Decomposition` | simultaneous multi-view decomposition, paper-cutout boundaries |

`Zero_Plane` is a **gate**, not a preference: below 0.40 the piece is not collage.

## GNV sidecars — provenance that survives
`six_axes/gnv_schema.py` writes a `gnv.json` beside any asset:

```json
{
  "gnv_id": "…", "sha256": "…", "created": "…",
  "six_axes": {"Material_Substrate": 0.82, "Exposure_Fracture": 0.74, "…": 0.0},
  "verdict": "canonical | reject",
  "lineage": {"parent": "…", "method": "…", "stage": "…"},
  "ownership": {"artist": "…", "chain": ["…"]}
}
```

Run it:
```bash
python six_axes/gnv_schema.py --image path/to/piece.jpg --axes 0.82,0.74,0.61,0.88,0.55,0.70 --out path/to/piece.gnv.json
```
(axes are supplied by the private scoring stack; this repo ships the *schema and the gate*, not the
weights.)

## The agent layer
`board_mcp/` contains a small **append-only agent board** plus an **MCP server** (SDK 2.0
`MCPServer`) that exposes it as six tools — `board_read`, `board_post`, `board_ack`, `board_digest`,
`board_stats`, `board_protocol`. Two agents (a local executor and a cloud architect) hand work to
each other through it, and **no human has to relay messages**:

```bash
pip install -r requirements.txt
python board_mcp/board_server.py            # serves over stdio
```

Design rule the board enforces: **silence is earned by acknowledging.** The delivery primitive
prints every row whose status is still `open`, so a failed notification re-sends instead of
vanishing.

## 3D reconstruction (AlphaOmega)
`alphaomega/forge_relief.py` is the approach we use to rebuild a flat collage as a
**source-textured volumetric relief** in headless Blender → USD: geometry authored from observed
silhouettes, source pixels projected as texture, front view = the exact collage, oblique view =
sculpture. Source frames are the artist's works and are **not included** here.

## How Nebius and NVIDIA are used in the full system
- **Nebius Token Factory** (`https://api.tokenfactory.nebius.com/v1`) runs the agent reasoning layer:
  `nvidia/nemotron-3-ultra-550b-a55b` as the always-on backbone, plus DeepSeek-V4 and Qwen3.5 models
  for evaluation. Feedback on the platform, including one real onboarding wall, is in the Devpost
  submission's required section.
- **NVIDIA open models & tooling**: Nemotron via NIM for interactive calls; **NVIDIA AI Workbench**
  as the development substrate on the workstation (we had to engineer around a
  `credential-manager.exe` bug that marks a valid key invalid — documented in the submission);
  CUDA + cuDNN, **TensorRT + ONNX Runtime GPU** for the art pipelines, **OptiX/OVRTX** for USD
  stage rendering, **NVENC** for the animation lane, **Ultralytics YOLO** for material/style
  detection.

## Measured result worth knowing
A Frobenius-norm decomposition of the fine-tuned diffusion checkpoint against its base shows
**> 98.7 % of the fine-tuning delta concentrated in ResNet convolutional kernels** (text encoder
ΔW_F = 6.59, cross-attention nearly untouched) — evidence that this style is an engine-level
physical substrate, and why attention-only LoRAs fail on it.

## Hygiene
Secrets never live in this repository: they are read from the environment. A pre-commit hook in the
parent project blocks credential-shaped strings from being staged, and a weekly sweep watches for
reappearance.

## Licence
Code: MIT (`LICENSE`). Artworks, model weights and the lineage vault are **not** part of this
repository and remain the artist's property.
