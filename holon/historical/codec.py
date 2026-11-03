"""`python -m holon historical codec`: the header carrier's edges on every real parent header of I59's window (the
contract is the docstring of tests_m2/test_historical_exit.py).

    python -m holon historical codec [--milestone M2] [--work DIR]

The corpus: every commit of I59's replay.json (results/<M>/historical/replay.json) with a "parent" or
"legacy_parent", in its order (block, transaction index). The header bytes are read back from the I59 snapshot: the
commit transaction's calldata decoded under the pinned ABI ("decoded") or under its historical signature
(abi_origin; holon.historical.abi), the parent header field of the target library (historical_target.json
parent_header); each must hash to the keccak replay.json records. A header's class is v<version>_<length>.

Edges (the frozen M0 header model, facts of the M0 registry; the real sides through I16's binding and harnesses,
replay/M2/implementations.json, unchanged):
  dec_go, ok_go, ok_sol   I59's comparisons, never re-run: a parent's go_decoder ("agree"/"disagree"; "not_run" is
                          not compared) for dec_go and ok_go, its pinned_solidity_ok_sol against the model's ok_sol
                          for ok_sol; a disagreement is a header I59's disagreements.json lists for that edge (dec_go,
                          ok_go) or whose pinned Solidity answer differs from the model's ok_sol (ok_sol).
  enc_sol                 the model's enc_sol against the real build block (op build) on H = dec_go(h) of every
                          decodable header (the model's ok_go true); H is the model's dec_go getters in the facts'
                          order, a getter the version skips filling zeros.
  enc_go_v0, enc_go_v1    the model against the real BatchHeaderV0.Bytes / BatchHeaderV1.Bytes (I16 binding) on H:
                          enc_go_v0 for version-0 headers, enc_go_v1 for versions 1 and 2.
reencode: the real Go encoder of the header's version (the enc_go_v0 output for version 0, enc_go_v1 for 1 and 2)
against the chain's bytes h, cell by cell, per class: {n, exact, diff_cells: {"<comma-joined cells>": n}}. A
cross-edge comparison (an encoder against bytes another implementation wrote), never a refinement disagreement.
blob_fallback: needed = the blobs I59 could not retrieve (replay.json summary.blobs: total - retrieved); run = 0 (the
L2 reconstruction fallback applies only to those; none is implemented here, so needed > 0 would be reported).

Outputs (canonical JSON): results/<M>/historical/codec.json and results/<M>/refinement/historical/<edge>.json (the
record format of holon.historical.trans, kind "historical"; implementation {harness, lang, target} of the binding).
A disagreement's id is holon.refinement.disagreement_id("historical.<edge>", <header keccak>); each new one is
appended to spec/<M>/disagreements.json as unexplained with no links and "milestone": "<M>".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import types
from pathlib import Path

from .. import ir
from ..keccak import keccak256
from .context import ContextError, Window, load_index

ROOT = Path(__file__).resolve().parents[2]
RECORD_VERSION = "holon-refinement/0.1"
I59_EDGES = ("dec_go", "ok_go", "ok_sol")
I23_EDGES = ("enc_go_v0", "enc_go_v1", "enc_sol")


def write(doc, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(ir.canonical_json(doc) + b"\n")
    tmp.replace(path)


def load_replay(milestone: str, root: Path) -> tuple[dict, Path]:
    p = Path(root) / "results" / milestone / "historical" / "replay.json"
    return load_index(p), p


def corpus(w: Window, rep: dict) -> list[dict]:
    """[{commit, key, bytes, version, length, keccak, parent}] of every parent header of replay.json, in its order."""
    from . import abi as A
    from . import target as TG
    from ..replay import check_checkout, morph_path, replay_config
    from .checks import model as header_model
    tgt = TG.load(w.milestone, w.root)
    hm = header_model(w.root)
    checkout = morph_path(types.SimpleNamespace(), w.root)
    sha = check_checkout(checkout, hm.facts["target"]["commit"])
    cfg = replay_config(w.root)
    pabi = A.PinnedAbi(checkout, sha, cfg["solc"], tgt)
    txs = {x["tx"]: x["sha256"] for x in w.idx["items"] if x["kind"] == "tx" and x["status"] == "ok"}
    out = []
    for c in rep["commits"]:
        key = "parent" if c.get("parent") else ("legacy_parent" if c.get("legacy_parent") else None)
        if key is None:
            continue
        p = c[key]
        tx = w.obj(txs[c["tx"]])
        data = bytes.fromhex(tx["input"][2:])
        sel = "0x" + data[:4].hex()
        if key == "parent":
            fn = pabi.pinned[sel]
        else:
            fn = pabi.legacy[sel][0]
        dec = A.decode(fn, data)
        first = next(iter(dec.values()))
        hb = bytes(first[tgt["parent_header"]])
        if "0x" + keccak256(hb).hex() != p["keccak"]:
            raise ContextError(f"{c['tx']}: the parent header read from the snapshot does not hash to replay.json's "
                               f"keccak {p['keccak']}")
        out.append({"commit": c, "key": key, "bytes": hb, "version": p["version"], "length": p["length"],
                    "keccak": p["keccak"], "parent": p})
    return out


def header_object(hm, hb: bytes, dec: list) -> dict:
    """H = dec_go(h) as a Header (field -> 0x-hex): the getters dec_go returns for the version, the rest zero."""
    obj = {n: "0x" + "00" * wd for n, wd in hm.widths.items()}
    names = hm.present(hb[0])
    if len(names) != len(dec):
        raise ContextError(f"dec_go gave {len(dec)} fields for {len(names)} getters")
    for n, v in zip(names, dec):
        obj[n] = v
    return obj


def model_view(hm, items: list[dict]) -> None:
    """Adds the model's ok_go, ok_sol and dec_go (as a Header, or None) to each corpus item."""
    hs = [it["bytes"] for it in items]
    for k in range(0, len(hs), 4000):
        rows = hm.check(hs[k:k + 4000])
        for it, row in zip(items[k:k + 4000], rows):
            it["ok_go"], it["ok_sol"] = row["ok_go"], row["ok_sol"]
            it["H"] = header_object(hm, it["bytes"], row["dec_go"]) if row["dec_go"] is not None else None


def i59_disagreements(root: Path, milestone: str) -> set:
    p = Path(root) / "results" / milestone / "historical" / "disagreements.json"
    doc = json.loads(p.read_text())
    return {(e["edge"], (e.get("input") or {}).get("keccak")) for e in doc.get("disagreements") or []}


def impl_ref(bind: dict, edge: str) -> dict:
    b = bind["edges"][edge]
    return {"harness": bind["harnesses"][b["lang"]]["path"], "lang": b["lang"], "target": b["target"]}


def run(milestone: str = "M2", root: Path = ROOT, work: Path | None = None) -> dict:
    from .. import refinement as R
    from ..replay import check_checkout, morph_path, toolchain
    from .checks import model as header_model
    w = Window(milestone, root)
    rep, rep_path = load_replay(milestone, root)
    hm = header_model(root)
    reg = ir.load_registry("M0", root)
    facts_rel = reg["facts"]
    bind = R.binding(root)
    items = corpus(w, rep)
    model_view(hm, items)
    by_class: dict = {}
    for it in items:
        k = f"v{it['version']}_{it['length']}"
        by_class[k] = by_class.get(k, 0) + 1
    dec_items = [it for it in items if it["ok_go"] and it["H"] is not None]
    # ---------------------------------------------------------------- I59's edges
    i59 = i59_disagreements(root, milestone)
    edges: dict = {}
    ids: dict = {e: [] for e in I59_EDGES + I23_EDGES}
    inputs: dict = {e: [] for e in I59_EDGES + I23_EDGES}
    for e in ("dec_go", "ok_go"):
        n = d = 0
        for it in items:
            g = it["parent"].get("go_decoder")
            if g not in ("agree", "disagree"):
                continue
            n += 1
            inputs[e].append(it["keccak"])
            if (e, it["keccak"]) in i59:
                d += 1
                did = R.disagreement_id(f"historical.{e}", it["keccak"])
                if did not in ids[e]:
                    ids[e].append(did)
            elif g == "disagree" and not any((x, it["keccak"]) in i59 for x in ("dec_go", "ok_go")):
                raise ContextError(f"{it['keccak']}: replay.json says the Go decoders disagree, I59's disagreements "
                                   "list it under neither edge")
        edges[e] = {"compared": n, "agree": n - d, "disagreements": d}
    n = d = 0
    for it in items:
        real = it["parent"].get("pinned_solidity_ok_sol")
        if real is None:
            continue
        n += 1
        inputs["ok_sol"].append(it["keccak"])
        if real != it["parent"]["ok_sol"]:
            d += 1
            did = R.disagreement_id("historical.ok_sol", it["keccak"])
            if did not in ids["ok_sol"]:
                ids["ok_sol"].append(did)
    edges["ok_sol"] = {"compared": n, "agree": n - d, "disagreements": d}
    # ---------------------------------------------------------------- the encoders (I23)
    corp = {"enc_sol": dec_items,
            "enc_go_v0": [it for it in dec_items if it["version"] == 0],
            "enc_go_v1": [it for it in dec_items if it["version"] in (1, 2)]}
    checkout = morph_path(types.SimpleNamespace(), root)
    check_checkout(checkout, hm.facts["target"]["commit"])
    tc = toolchain(types.SimpleNamespace(forge=None, solc=None, write_pins=False), root)
    model_out = {}
    for e in I23_EDGES:
        xs = [it["H"] for it in corp[e]]
        model_out[e] = [v for k in range(0, len(xs), 4000) for v in R.evaluate(hm.model, hm.facts, e, xs[k:k + 4000])]
    tmp = None
    if work is None:
        tmp = work = Path(tempfile.mkdtemp(prefix="holon-i23-codec-"))
    try:
        real = R.real_outputs(root, hm.facts, bind, list(I23_EDGES), {e: [it["H"] for it in corp[e]] for e in I23_EDGES},
                              checkout, Path(work), tc)
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
    new = []
    for e in I23_EDGES:
        n = len(corp[e])
        d = 0
        for it, mv, rv in zip(corp[e], model_out[e], real[e]):
            inputs[e].append(it["keccak"])
            if ir.canonical_json(mv) != ir.canonical_json(rv):
                d += 1
                did = R.disagreement_id(f"historical.{e}", it["keccak"])
                if did not in ids[e]:
                    ids[e].append(did)
                    new.append({"id": did, "edge": e, "milestone": milestone,
                                "input": {"keccak": it["keccak"], "length": it["length"]},
                                "model_sha256": R.sha256_json(mv), "real_sha256": R.sha256_json(rv)})
        edges[e] = {"compared": n, "agree": n - d, "disagreements": d,
                    "outputs_sha256": {"model": R.sha256_json(model_out[e]), "real": R.sha256_json(real[e])}}
    for e in I59_EDGES:
        for did in ids[e]:
            new.append({"id": did, "edge": e, "milestone": milestone, "input": {"source": "i59"}})
    # ---------------------------------------------------------------- reencode (cross-edge, never a disagreement)
    reenc: dict = {}
    real_of = {}
    for e in ("enc_go_v0", "enc_go_v1"):
        for it, rv in zip(corp[e], real[e]):
            real_of[id(it)] = rv
    for it in dec_items:
        rv = real_of.get(id(it))
        if rv is None:
            continue
        k = f"v{it['version']}_{it['length']}"
        o = reenc.setdefault(k, {"n": 0, "exact": 0, "diff_cells": {}})
        rb, hb = bytes.fromhex(rv[2:]), it["bytes"]
        cells = [i for i in range(max(len(rb), len(hb))) if i >= len(rb) or i >= len(hb) or rb[i] != hb[i]]
        o["n"] += 1
        if not cells:
            o["exact"] += 1
        else:
            key = ",".join(str(c) for c in cells)
            o["diff_cells"][key] = o["diff_cells"].get(key, 0) + 1
    # ---------------------------------------------------------------- records
    if new:
        R.append_disagreements(root, new)
    entries = {x["id"]: x for x in json.loads((Path(root) / R.DISAGREEMENTS).read_text())["disagreements"]}
    diag = {fn: did for fn, _k, did in R.refined_edges(facts_rel, root)}
    facts_sha = hashlib.sha256((Path(root) / facts_rel).read_bytes()).hexdigest()
    window = w.window("codec")
    dis = []
    out_edges = {}
    for e in sorted(I59_EDGES + I23_EDGES):
        rec = {"record_version": RECORD_VERSION, "kind": "historical", "milestone": milestone, "edge": e,
               "diagram_edge": diag.get(e), "facts": facts_rel, "facts_sha256": facts_sha,
               "corpus": {"source": "historical", "window": window, "inputs": len(inputs[e]),
                          "inputs_sha256": R.sha256_json(inputs[e])},
               "compared": edges[e]["compared"], "agree": edges[e]["agree"],
               "disagreements": edges[e]["disagreements"], "disagreement_ids": sorted(ids[e]), "fixes": [],
               "implementation": impl_ref(bind, e), "real_source": "i59" if e in I59_EDGES else "i23"}
        if "outputs_sha256" in edges[e]:
            rec["outputs_sha256"] = edges[e]["outputs_sha256"]
        path = Path(root) / "results" / milestone / "refinement" / "historical" / f"{e}.json"
        write(rec, path)
        out_edges[e] = {"compared": rec["compared"], "agree": rec["agree"], "disagreements": rec["disagreements"],
                        "source": rec["real_source"], "implementation": rec["implementation"],
                        "record": path.relative_to(root).as_posix()}
        for did in rec["disagreement_ids"]:
            dis.append({"id": did, "edge": e, "class": R.classify(entries[did], root) if did in entries
                        else "unexplained", "links": (entries.get(did) or {}).get("links", {})})
    blobs = (rep.get("summary") or {}).get("blobs") or {}
    doc = {"window": window,
           "replay": {"path": rep_path.relative_to(root).as_posix(),
                      "sha256": hashlib.sha256(rep_path.read_bytes()).hexdigest()},
           "corpus": {"parents": len(items), "by_class": dict(sorted(by_class.items())), "decodable": len(dec_items),
                      "inputs_sha256": R.sha256_json([it["keccak"] for it in items])},
           "edges": out_edges,
           "reencode": {k: {"n": v["n"], "exact": v["exact"], "diff_cells": dict(sorted(v["diff_cells"].items()))}
                        for k, v in sorted(reenc.items())},
           "disagreements": dis, "unexplained": sum(1 for d in dis if d["class"] == "unexplained"),
           "blob_fallback": {"needed": int(blobs.get("total", 0)) - int(blobs.get("retrieved", 0)), "run": 0}}
    return doc


def main(argv=None) -> int:
    from .. import refinement as R
    ap = argparse.ArgumentParser(prog="holon historical codec")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--work")
    a = ap.parse_args(argv)
    try:
        doc = run(a.milestone, ROOT, Path(a.work) if a.work else None)
    except (ContextError, R.RefineError) as e:
        print(f"historical codec: {e}", file=sys.stderr)
        return 2
    out = ROOT / "results" / a.milestone / "historical" / "codec.json"
    write(doc, out)
    print(json.dumps({"corpus": doc["corpus"], "edges": {k: {x: v[x] for x in ("compared", "agree", "disagreements")}
                                                         for k, v in doc["edges"].items()},
                      "reencode": doc["reencode"], "unexplained": doc["unexplained"]}, sort_keys=True))
    print(f"wrote {out}")
    return 0 if not doc["disagreements"] else 1
