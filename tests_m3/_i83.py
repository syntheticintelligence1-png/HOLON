"""I83's instrument (fixed at the prereg; the contract is the docstring of tests_m3/test_versions_debt.py).

It is written independently of holon/: it reads committed JSON only (I63's history, I28's basis and sidecar, the
deployment record, I28's per-version documents), and where it needs what I28's instrument already computes (the
chains of rule PI1, the in-flight words of rule V8) it calls tests_m3/_i28.py, fixed at I28's prereg. It computes:

  edges(root)                 the MIG edges of the deployed path, in path order, with the reinitializer each introduces
  trace_labels(root, a, b)    rule IS1's labels of edge a -> b's in-flight trace: the upgrade path's prefix up to a
                              (the entry edge, the deployment record's first calls by their function names at the
                              path's first version, each MIG edge before a), the first successor-site action of a in
                              name order (rule PI1 over a's document: tests_m3/_i28.py::chains), then the edge
  genesis_key(root)           the batch index a commit on top of the recorded genesis batch writes (its index + 1)
  stand_in(root)              the binding's submitter stand-in: the first word argument of the deployment record's
                              first call (I28's sidecar names it for initialize4)
  committed_slot(root, v, k)  the real slot of the committed family's entry k at version v (keccak256(k . slot), the
                              family's slot in I63's layout of v; the family is the one chain of rule PI1)
  havoc_versions(root)        the path versions before the head whose first successor action's write of the committed
                              family holds a memory region with a ["loop", ..] entry (a loop's writes the frontend
                              does not summarise): the versions where model3's value of that write cannot be the
                              chain's (model3 havocs such a region: holon/sorts/model3.py's mem_write, at I28's base)
  basis_doc(root)             the values the key's thresholds state, from the above
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import tests_m3._i28 as I28

ROOT = Path(__file__).resolve().parents[1]
VERSIONS_SIDECAR = "spec/M3/lib/versions.json"
VERSIONS_BASIS = "spec/M3/lib/versions_basis.json"
VERSIONED_DOCUMENT = "gen/M3/versions/morph_rollup.versions.json"
DEPLOYMENT = "gen/M3/sorts/models/morph_rollup.extracted.init.json"
HISTORY = "gen/M3/history/morph_rollup.json"
PLACEHOLDER = "placeholder"


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _word(n: int) -> bytes:
    return (int(n) % (1 << 256)).to_bytes(32, "big")


def basis(root: Path = ROOT) -> dict:
    return load(Path(root) / VERSIONS_BASIS)


def path(root: Path = ROOT) -> list:
    return list(basis(root)["path"])


def edges(root: Path = ROOT) -> list:
    """[(a, b, [the reinitializers the edge introduces])] of the MIG edges of the deployed path, in path order."""
    return [(e["from"], e["to"], [r["name"] for r in e.get("introduced") or []]) for e in basis(root)["edges"]]


def document(root: Path, version: str) -> tuple[Path, dict]:
    """I28's extracted transitions document of a path version (the versioned document names it)."""
    vd = load(Path(root) / VERSIONED_DOCUMENT)
    rel = vd["documents"][version]["path"]
    return Path(root) / rel, load(Path(root) / rel)


def function_name(root: Path, version: str, calldata: str) -> str:
    """The name of the version's function whose selector the calldata's first four bytes are."""
    sel = (calldata[2:] if calldata.startswith("0x") else calldata)[:8].lower()
    _p, doc = document(root, version)
    names = [a["name"] for a in doc["actions"] if (a.get("selector") or "").lower().removeprefix("0x") == sel]
    if len(names) != 1:
        raise ValueError(f"{version}: {len(names)} functions have selector 0x{sel}")
    return names[0]


def successor_actions(root: Path, version: str) -> list:
    """Rule PI1's successor-site actions of the version's document (tests_m3/_i28.py::chains), in name order."""
    p, _doc = document(root, version)
    ch = I28.chains(p)
    return sorted({s["action"] for f in ch["families"] for s in f["successor_sites"]})


def committed_family(root: Path, version: str) -> str:
    p, _doc = document(root, version)
    fams = [f["family"] for f in I28.chains(p)["families"]]
    if len(fams) != 1:
        raise ValueError(f"{version}: {len(fams)} commitment families")
    return fams[0]


def trace_labels(root: Path, a: str, b: str) -> list:
    """Rule IS1: the labels of edge a -> b's in-flight trace."""
    root = Path(root)
    side = load(root / VERSIONS_SIDECAR)
    dep = load(root / DEPLOYMENT)
    pth = path(root)
    first = pth[0]
    labels = ["entry"] + [function_name(root, first, dep["calls"][i]["data"])
                          for i in side["upgrade_path"]["first_calls"]]
    for x, y, _r in edges(root):
        if x == a:
            break
        labels.append(f"{x}->{y}")
    return labels + [successor_actions(root, a)[0], f"{a}->{b}"]


def genesis_key(root: Path = ROOT) -> int:
    """The index a commit on top of the recorded genesis batch writes: the genesis header's index (bytes 1..8) + 1 (the
    header is the bytes argument of the deployment record's call the upgrade path makes last among its first calls)."""
    root = Path(root)
    side = load(root / VERSIONS_SIDECAR)
    dep = load(root / DEPLOYMENT)
    cd = bytes.fromhex(dep["calls"][side["upgrade_path"]["first_calls"][-1]]["data"][2:])[4:]
    off = int.from_bytes(cd[0:32], "big")
    n = int.from_bytes(cd[off:off + 32], "big")
    header = cd[off + 32:off + 32 + n]
    return int.from_bytes(header[1:9], "big") + 1


def stand_in(root: Path = ROOT) -> int:
    dep = load(Path(root) / DEPLOYMENT)
    cd = bytes.fromhex(dep["calls"][0]["data"][2:])
    return int.from_bytes(cd[4:36], "big")


def layout_slot(root: Path, version: str, label: str) -> int:
    h = load(Path(root) / HISTORY)
    v = next(x for x in h["versions"] if x["id"] == version)
    es = [e for e in v["layout"] if e["label"] == label]
    if len(es) != 1:
        raise ValueError(f"{version}: {len(es)} layout entries labelled {label}")
    return int(es[0]["slot"])


def committed_slot(root: Path, version: str, key: int) -> int:
    from tests_m2._keccak import keccak256
    slot = layout_slot(root, version, committed_family(root, version))
    return int.from_bytes(keccak256(_word(key) + _word(slot)), "big")


def _has_loop_region(t) -> bool:
    if isinstance(t, list):
        if t and t[0] == "mem" and any(isinstance(w, list) and w[:1] == ["loop"] for w in t[1:]):
            return True
        return any(_has_loop_region(x) for x in t)
    if isinstance(t, dict):
        return any(_has_loop_region(x) for x in t.values())
    return False


def havoc_versions(root: Path = ROOT) -> list:
    """The path versions before the head whose first successor action writes the committed family with a value that
    reads a memory region holding a ["loop", ..] entry (I28's documents; the head's code is the last path version)."""
    out = []
    pth = path(root)
    for v in pth[:-1]:
        _p, doc = document(root, v)
        fam = committed_family(root, v)
        act = next(a for a in doc["actions"] if a["name"] == successor_actions(root, v)[0])
        ws = [w for w in act.get("writes") or [] if w.get("family") == fam]
        if any(_has_loop_region(w.get("value")) for w in ws):
            out.append(v)
    return out


def inflight_words(root: Path, a: str, b: str, key: int) -> list:
    """Rule V8's legacy words of edge a -> b at the key (tests_m3/_i28.py::inflight_words)."""
    return I28.inflight_words(Path(root), a, b, key)


def basis_doc(root: Path = ROOT) -> dict:
    """The values the key's thresholds state."""
    root = Path(root)
    key = genesis_key(root)
    labels = {f"{a}->{b}": trace_labels(root, a, b) for a, b, _r in edges(root)}
    hv = havoc_versions(root)
    return {"trace_labels": labels,
            "trace_lengths": {e: len(x) for e, x in labels.items()},
            "key": key,
            "stand_in": "0x%040x" % stand_in(root),
            "cutover_legacy_reads": [w["reads"] for w in inflight_words(root, *edges(root)[-1][:2], key)],
            "havoc_versions": hv,
            "havoc_slots": {v: "0x%064x" % committed_slot(root, v, key) for v in hv},
            "replay_pass_edges": [f"{a}->{b}" for a, b, _r in edges(root) if a not in hv],
            "replay_one_slot_edges": [f"{a}->{b}" for a, b, _r in edges(root) if a in hv]}
