"""GNV sidecar builder — provenance for any asset: sha256 + six-axis vector + verdict + lineage.

A GNV record is the machine-readable identity of a piece: what it is (hash), how it reads on the
six axes, whether it passes the Zero_Plane gate, and where it came from.

Usage
-----
python six_axes/gnv_schema.py --image piece.jpg --axes 0.82,0.74,0.61,0.88,0.55,0.70 --out piece.gnv.json
python six_axes/gnv_schema.py --image piece.jpg --axes ... --parent <gnv_id> --method "sdxl-dora-r32/v70"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone

try:
    from .axes import AXES, parse_cli, verdict, explain   # package import
except ImportError:                                        # direct script run
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from axes import AXES, parse_cli, verdict, explain


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(image: str, scores: dict[str, float], *, parent: str | None = None,
          method: str | None = None, stage: str = "render", artist: str = "") -> dict:
    digest = sha256_file(image)
    return {
        "gnv_id": f"gnv-{digest[:12]}",
        "sha256": digest,
        "created": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "asset": {"file": os.path.basename(image), "bytes": os.path.getsize(image)},
        "six_axes": scores,
        "verdict": verdict(scores),
        "lineage": {"parent": parent, "method": method, "stage": stage},
        "ownership": {"artist": artist, "chain": [f"gnv-{digest[:12]}"]},
        "schema": "gnv/1",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Write a GNV sidecar (sha256 + six axes + verdict + lineage).")
    p.add_argument("--image", required=True)
    p.add_argument("--axes", required=True, help="six values 0.00–1.00 in canonical order")
    p.add_argument("--out", default=None)
    p.add_argument("--parent", default=None)
    p.add_argument("--method", default=None)
    p.add_argument("--stage", default="render")
    p.add_argument("--artist", default="")
    a = p.parse_args(argv)

    scores = parse_cli(a.axes)
    rec = build(a.image, scores, parent=a.parent, method=a.method, stage=a.stage, artist=a.artist)
    out = a.out or os.path.splitext(a.image)[0] + ".gnv.json"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False)
    print(explain(scores))
    print(f"\nwrote {out}")
    print(f"gnv_id  {rec['gnv_id']}")
    print(f"sha256  {rec['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
