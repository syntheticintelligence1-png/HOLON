"""Evaluate the generated model by compiling it with the pinned Bend and running it in node.

The artifact executed is exactly `bend <source> -o <artifact>.mjs`; Python only moves
values in and out (canonical JSON <-> Bend values). Nothing is evaluated in Python.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from . import bend
from . import facts as F
from .gen import model as G

ROOT = Path(__file__).resolve().parents[1]
DRIVER = Path(__file__).resolve().parent / "js" / "eval.mjs"


class ModelError(Exception):
    pass


def model_name(facts_path: str | Path) -> str:
    """Bend module names are plain words: derive one from the facts file name."""
    return re.sub(r"[^A-Za-z0-9_]", "_", Path(facts_path).stem) or "model"


def write_if_changed(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != text:
        path.write_text(text)


class CompiledModel:
    """A generated model source plus its compiled ES module."""

    def __init__(self, source: Path, artifact: Path, facts: dict):
        self.source, self.artifact, self.facts = Path(source), Path(artifact), facts

    @property
    def artifact_sha256(self) -> str:
        return hashlib.sha256(self.artifact.read_bytes()).hexdigest()

    @classmethod
    def build(cls, facts_path, source: Path | None = None, cfg: dict | None = None) -> "CompiledModel":
        facts_path = Path(facts_path)
        facts = F.load(facts_path)
        sha = F.sha256_file(facts_path)
        text = G.generate(facts, sha)
        if source is None:
            source = bend.build_dir(ROOT) / "eval" / sha[:16] / f"{model_name(facts_path)}.bend"
        source = Path(source)
        write_if_changed(source, text)
        artifact = source.with_suffix(".mjs")
        stamp = source.with_suffix(".src.sha256")
        src_sha = hashlib.sha256(text.encode()).hexdigest()
        if not (artifact.exists() and stamp.exists() and stamp.read_text() == src_sha):
            r = bend.run([source.name, "-o", artifact.name], cwd=source.parent, cfg=cfg)
            if r.code != 0 or not artifact.exists():
                raise ModelError(f"bend failed to compile {source}: {r.out[:2000]}")
            stamp.write_text(src_sha)
        return cls(source, artifact, facts)

    def run_jobs(self, jobs: list[dict], timeout: int = 600) -> list[list]:
        if not jobs:
            return []
        node = bend.config().get("node", "node")
        p = subprocess.run([node, str(DRIVER)], input=json.dumps({"module": str(self.artifact), "jobs": jobs}),
                           capture_output=True, text=True, timeout=timeout)
        if p.returncode != 0:
            raise ModelError(f"node evaluation failed: {p.stderr[-2000:]}")
        return json.loads(p.stdout)["results"]


# ---------------------------------------------------------------- value conversion
def header_in(facts: dict, obj: dict) -> dict:
    w = F.widths(facts)
    if set(obj) != set(w):
        raise ValueError(f"header fields differ: {sorted(set(obj) ^ set(w))}")
    cells = {}
    for name, width in w.items():
        b = bytes.fromhex(obj[name][2:])
        if len(b) != width:
            raise ValueError(f"{name}: {len(b)} bytes, expected {width}")
        cells.update({f"{name}_{k}": b[k] for k in range(width)})
    return {"$hdr": cells}


def bytes_in(s: str) -> list[int]:
    return list(bytes.fromhex(s[2:]))


def value_in(ir_type: str, v, facts: dict):
    return header_in(facts, v) if ir_type == "Header" else bytes_in(v)


def _hex(xs: list[int]) -> str:
    if any(not (0 <= x <= 255) for x in xs):
        raise ValueError("undefined")
    return "0x" + bytes(xs).hex()


def value_out(ir_type: str, v):
    """Canonical JSON of a decoded model value; raises ValueError('undefined') on 0xDEAD bytes."""
    if isinstance(v, dict) and "error" in v:
        raise ModelError(v["error"])
    if ir_type == "Bytes":
        return _hex(v)
    if ir_type == "Bool":
        return bool(v)
    if ir_type == "Fields":
        return [_hex(x) for x in v]
    if ir_type == "MaybeFields":
        return None if v is None else [_hex(x) for x in v["$some"]]
    raise ValueError(ir_type)


def eval_batch(fn: str, inputs: list, facts_path: str | None = None) -> dict:
    facts_path = facts_path or str(ROOT / "facts" / "morph_header.json")
    m = CompiledModel.build(facts_path)
    arg_t, res_t = F.fn_types(m.facts, fn)
    jobs = [{"terms": [{"call": fn, "args": [{"var": "x"}]}], "env": {"x": value_in(arg_t, x, m.facts)}}
            for x in inputs]
    outs = []
    for (v,) in m.run_jobs(jobs):
        try:
            outs.append(value_out(res_t, v))
        except ValueError:
            outs.append({"undefined": True})
    ver = bend.version()
    return {"engine": f"bend-{ver}-mjs-node", "source": str(m.source), "artifact": str(m.artifact),
            "artifact_sha256": m.artifact_sha256, "outputs": outs}
