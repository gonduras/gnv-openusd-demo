"""The six canonical axes of GONDURASTRATION — definitions, validation and the Zero_Plane gate.

Public demo slice: the *schema and the gate*, not the scoring weights (those stay in the
private vault). Constants here are the same ones the private stack uses.
"""
from __future__ import annotations

AXES = (
    "Material_Substrate",     # litho ink density, newsprint grain, tape residue, resin sheen
    "Exposure_Fracture",      # scorched Mediterranean light, extreme directional shadow cuts
    "Structural_Glitch",      # anti-retinal disruption, substrate tears, epoxy borders
    "Graphic_Vector",         # diagonal spatial geometry, high-density vector composition
    "Zero_Plane",             # non-objective zero-degree field, floating primitives
    "Faceted_Decomposition",  # simultaneous multi-view decomposition, paper-cutout boundaries
)

ZERO_PLANE_REJECT = 0.40   # hard canonical reject below this


class AxisError(ValueError):
    """Raised when a score vector does not match the canonical schema."""


def validate(scores: dict[str, float]) -> dict[str, float]:
    """Return a normalised six-axis dict or raise AxisError."""
    if set(scores) != set(AXES):
        missing = set(AXES) - set(scores)
        extra = set(scores) - set(AXES)
        raise AxisError(f"six-axis schema mismatch (missing={sorted(missing)}, extra={sorted(extra)})")
    out = {}
    for k, v in scores.items():
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise AxisError(f"{k}: not a number: {v!r}")
        if not 0.0 <= f <= 1.0:
            raise AxisError(f"{k}: out of range 0.00–1.00: {f}")
        out[k] = round(f, 4)
    return out


def verdict(scores: dict[str, float]) -> str:
    """`reject` when Zero_Plane is below the gate, else `canonical`."""
    s = validate(scores)
    return "reject" if s["Zero_Plane"] < ZERO_PLANE_REJECT else "canonical"


def explain(scores: dict[str, float]) -> str:
    s = validate(scores)
    lines = [f"{k:24} {s[k]:.2f}  {'#' * int(round(s[k] * 20))}" for k in AXES]
    v = verdict(s)
    lines.append(f"\nverdict: {v.upper()}" +
                 (f"  (Zero_Plane {s['Zero_Plane']:.2f} < {ZERO_PLANE_REJECT} — photographic/contaminated)"
                  if v == "reject" else ""))
    return "\n".join(lines)


def parse_cli(spec: str) -> dict[str, float]:
    """Parse `0.82,0.74,0.61,0.88,0.55,0.70` in canonical axis order."""
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    if len(parts) != len(AXES):
        raise AxisError(f"expected {len(AXES)} comma-separated values in canonical order, got {len(parts)}")
    return validate(dict(zip(AXES, (float(p) for p in parts))))


if __name__ == "__main__":
    demo = {"Material_Substrate": 0.82, "Exposure_Fracture": 0.74, "Structural_Glitch": 0.61,
            "Graphic_Vector": 0.88, "Zero_Plane": 0.55, "Faceted_Decomposition": 0.70}
    print(explain(demo))
    print("\ncontaminated example (Zero_Plane 0.21):")
    print(verdict({**demo, "Zero_Plane": 0.21}))
