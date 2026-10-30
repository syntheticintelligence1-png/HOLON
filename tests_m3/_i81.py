"""I81's instrument (the prereg sidecar of key I81; written without holon's measure or ranking code, and importing
nothing from holon/). It decides the key's predictions two ways:

1. Independent computations over the committed inputs, by this module's own reading of the contract's rules (the
   docstring of tests_m3/test_ranking.py):
   - par_positions: the positions where a REFUTED PAR record's difference sides differ (the measure's lower bound);
   - layout_bound: the positions where the two encoders' layouts of a codec document can differ under the law's
     premises (field correspondences and constant pins), plus any length difference (the measure's upper bound);
   - undo_divergence: the first step of the continuation t where the model's observations of the two runs differ, in
     replay/<M>/undo/report.json;
   - schedule, reach_of, cost_of: rules RE1-RE3 and CO1 over the witness schedules, the concretization paths and the
     principal classes of gen/<M>/disch/closure.json;
   - channel_of, persistence_of: rules K1-K8 and PE1-PE3.
2. The predicted values, fixed here at the prereg (EXPECTED, ORDER, KINDS), and the analogue map of whitepaper
   §11.3's Impact column (IMPACT), with the vocabulary the comparison uses (REACH_WORDS, PERSISTENCE_WORDS).

The analogue map is a human reading of §11.3 against today's M3 laws (which O-row each law's obstruction is); it lives
here, never in holon/, and only the comparison of the computed classes with it uses it.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = "M3"
BASE = "00b12f70"   # the lead after I28's build merge (PR #50): 136 M3 laws
GO_PANIC = "OPanic"  # the panic outcome of a Go-op model (holon.gen.goloop's Out type, read here as data)


def load(p) -> dict:
    return json.loads(Path(p).read_text())


def sidecar(root: Path = ROOT) -> dict:
    return load(root / "spec" / M / "lib" / "ranking.json")


# ------------------------------------------------------------------ PAR: holonomy defect size
def _hexbytes(v):
    if isinstance(v, str) and v.startswith("0x"):
        try:
            return bytes.fromhex(v[2:])
        except ValueError:
            return None
    return None


def par_positions(record: dict) -> list[int]:
    """The positions where the difference's two sides differ: byte positions for two byte strings (the common prefix's
    differing bytes, then every position of the longer one past the shorter); [0] for any other unequal pair."""
    d = record.get("difference") or {}
    a, b = d.get("lhs"), d.get("rhs")
    ba, bb = _hexbytes(a), _hexbytes(b)
    if ba is not None and bb is not None:
        n = min(len(ba), len(bb))
        return [i for i in range(n) if ba[i] != bb[i]] + list(range(n, max(len(ba), len(bb))))
    return [] if a == b else [0]


def _version_pins(assume: list) -> dict:
    """{var: version int} from the premises version == <bytes>."""
    out = {}
    for p in assume:
        l, r = p["eq"]
        if isinstance(l, dict) and l.get("field") == "version" and "of" in l and "bytes" in r:
            out[l["of"]["var"]] = int(r["bytes"], 16)
    return out


def layout_bound(law: dict, codec: dict) -> list[int] | None:
    """The positions where the claim's two encoder layouts can differ under the premises, or None when the claim is
    not two encoders of the codec document with a layout at the premises' version."""
    st = law["statement"]
    lhs, rhs = st["claim"]["eq"]
    if not all(isinstance(s, dict) and "call" in s for s in (lhs, rhs)):
        return None
    fns = codec.get("functions") or {}
    vers = _version_pins(st.get("assume") or [])
    sides = []
    for s in (lhs, rhs):
        f = fns.get(s["call"])
        if not f or f.get("kind") != "encoder" or "layouts" not in f:
            return None
        var = s["args"][0]["var"]
        if f.get("versions") is None:
            lay = next(iter(f["layouts"].values()))
        else:
            if var not in vers or str(vers[var]) not in f["layouts"]:
                return None
            lay = f["layouts"][str(vers[var])]
        sides.append((var, lay))
    parent: dict = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    pins: dict = {}
    for p in st.get("assume") or []:
        l, r = p["eq"]
        if "field" in l and "field" in r:
            a, b = find((l["of"]["var"], l["field"])), find((r["of"]["var"], r["field"]))
            if a != b:
                parent[max(a, b)] = min(a, b)
        elif "field" in l and "bytes" in r:
            pins[(l["of"]["var"], l["field"])] = bytes.fromhex(r["bytes"][2:])
    pinned = {}
    for k, v in pins.items():
        pinned[find(k)] = v

    def norm(var, cell, i, side):
        if cell[0] == "field":
            rep = find((var, cell[1]))
            if rep in pinned:
                return ("const", pinned[rep][cell[2]])
            return ("field", rep, cell[2])
        if cell[0] == "const":
            return ("const", cell[1])
        return ("opaque", side, i)
    (va, la), (vb, lb) = sides
    n = min(len(la), len(lb))
    out = [i for i in range(n) if norm(va, la[i], i, 0) != norm(vb, lb[i], i, 1)]
    return out + list(range(n, max(len(la), len(lb))))


def ranges(ps: list[int]) -> list[list[int]]:
    out: list[list[int]] = []
    for p in sorted(ps):
        if out and out[-1][1] == p - 1:
            out[-1][1] = p
        else:
            out.append([p, p])
    return out


# ------------------------------------------------------------------ UNDO: residue liveness distance
def undo_divergence(entry: dict) -> int | None:
    """The first index i of t where the model observes the two runs differently (the run with the pair at t_at + i,
    the run without it at t_at - 2 + i), or None."""
    w, wo = entry["with"]["model"], entry["without"]["model"]
    t_at = entry["t_at"]
    pre = t_at - 2
    n = len(entry["with"]["trace"]) - t_at
    for i in range(n):
        if w[t_at + i] != wo[pre + i]:
            return i
    return None


# ------------------------------------------------------------------ schedules, reach, cost (RE1-RE3, CO1)
def doc_actions(root: Path, rel: str) -> dict:
    return {a["name"]: a for a in load(root / rel).get("actions") or []}


def classes(root: Path = ROOT) -> dict:
    """{class id: predicate} and {action: class id} of the DISCH closure document (I31's principal classes)."""
    d = load(root / "gen" / M / "disch" / "closure.json")
    preds, of = {}, {}
    for _m, md in sorted(d["models"].items()):
        for cid, c in sorted(md["classes"].items()):
            preds[cid] = c.get("predicate")
            for a in c.get("actions") or []:
                of.setdefault(a, cid)
    return {"pred": preds, "of": of}


def _holds(t, head) -> bool:
    if isinstance(t, list):
        return (bool(t) and t[0] == head) or any(_holds(x, head) for x in t)
    return False


def _caller_map(t) -> bool:
    if isinstance(t, list):
        if len(t) == 3 and t[0] == "map" and t[2] == ["caller"]:
            return True
        return any(_caller_map(x) for x in t)
    return False


def pred_kind(pred) -> str:
    if pred is None:
        return "anyone"
    if _holds(pred, "sload"):
        return "slot"
    if isinstance(pred, list) and pred and pred[0] == "call":
        return "call"
    if _caller_map(pred):
        return "mapping"
    if isinstance(pred, list) and pred and pred[0] == "==" and ["caller"] in pred[1:] \
            and any(isinstance(x, list) and x[:1] == ["storage"] for x in pred[1:]):
        return "owner"
    return "undecided"


def schedule(law: dict, record: dict, conc: dict) -> tuple[list | None, str | None]:
    """(the steps the witness schedule holds, or None; the pending key when the schedule waits on one)."""
    w = record.get("witness") or {}
    rule, claim = law["rule"], law["statement"]["claim"]["eq"][0]
    if rule == "UNDO":
        return list(w.get("prefix") or []) + [w["x"], w["y"]] + list(w.get("t") or []), None
    if rule == "FACT":
        if "runs" in w:
            out = []
            for r in w["runs"]:
                out += list(r.get("prefix") or []) + [r["x"]]
            return out, None
        return list(w.get("prefix") or []) + [w["y"]] + list(w.get("t") or []), None
    if rule in ("SORT", "DISCH"):
        return list(w.get("steps") or []), None
    if rule == "PAR" and isinstance(claim, dict) and "init" in claim:
        return [s for s in w.get("trace") or [] if s.get("kind") == "call"], None
    c = (conc.get("records") or {}).get(f"{M}/{law['law_id']}") or {}
    if c.get("result") == "path":
        return list(c.get("path") or []), None
    pend = sidecar().get("pending_reach") or {}
    if c.get("kind") in pend:
        return None, pend[c["kind"]]
    return None, None


def reach_of(steps, pending, cls: dict, sc: dict) -> dict:
    if steps is None:
        return {"class": None, "kind": "pending" if pending else "undecided", "pending": pending}
    tiers = [x for t in sc["reach_order"] for x in t]
    best = None
    for s in steps:
        cid = cls["of"].get(s.get("action"), "anyone")
        k = pred_kind(cls["pred"].get(cid))
        key = (tiers.index(k), cid)
        if best is None or key[0] > best[0][0] or (key[0] == best[0][0] and cid < best[1]):
            best = (key, cid, k)
    if best is None:
        return {"class": None, "kind": "undecided", "pending": None}
    return {"class": best[1], "kind": best[2], "pending": None}


def cost_of(steps, acts: dict) -> int | None:
    if steps is None:
        return None
    return sum(1 for s in steps if (acts.get(s.get("action")) or {}).get("mutability") not in ("view", "pure"))


# ------------------------------------------------------------------ channels and persistence (K1-K8, PE1-PE3)
def channel_of(law: dict, record: dict, root: Path = ROOT) -> str:
    rule, st = law["rule"], law["statement"]
    claim = st["claim"]["eq"][0]
    if record.get("triage") == "intent_question":
        return "intent"
    if rule == "DISCH":
        return "guard"
    if rule == "UNDO":
        e = (load(root / "replay" / M / "undo" / "report.json").get("laws") or {}).get(law["law_id"])
        if not e:
            return "undecided"
        i = undo_divergence(e)
        if i is None:
            return "undecided"
        acts = doc_actions(root, law["facts"])
        step = e["with"]["trace"][e["t_at"] + i]
        if (acts.get(step.get("action")) or {}).get("mutability") in ("view", "pure"):
            return "view"
        a, b = e["with"]["model"][e["t_at"] + i], e["without"]["model"][e["t_at"] - 2 + i]
        return "revert" if a.get("status") != b.get("status") else "store"
    if rule == "FACT":
        fid = claim.get("fact", "")
        parts = fid.split(":")
        if parts[1:2] == ["attribution"]:
            return "attribution"
        doc = load(root / law["facts"])
        fams = {s.get("name") for s in (doc.get("storage") or []) + (doc.get("inherited_storage") or [])}
        return "store" if parts[-1] in fams else "commitment"
    if rule == "SORT":
        e = (load(root / "replay" / M / "sorts" / "report.json").get("laws") or {}).get(law["law_id"])
        if not e:
            return "undecided"
        ends = [x["model"][-1].get("status") for x in e["entries"].values() if x.get("model")]
        return "revert" if "revert" in ends else "store"
    if rule == "PAR":
        if law["facts"].startswith(f"gen/{M}/goops/"):
            d = record.get("difference") or {}
            return "abort" if any(v is False or v == GO_PANIC for v in (d.get("lhs"), d.get("rhs"))) \
                else "representation"
        if isinstance(claim, dict) and "init" in claim:
            return "store"
        lhs, rhs = st["claim"]["eq"]
        if all(isinstance(s, dict) and "call" in s for s in (lhs, rhs)):
            fns = load(root / law["facts"]).get("functions") or {}

            def fn(name):   # ok_<f> is the model's domain predicate of f
                return fns.get(name) or (fns.get(name[3:]) if name.startswith("ok_") else None) or {}
            fa, fb = fn(lhs["call"]), fn(rhs["call"])
            if fa.get("lang") and fb.get("lang"):
                return "representation" if fa["lang"] != fb["lang"] else "store"
        return "undecided"
    return "undecided"


def persistence_of(law: dict, root: Path = ROOT) -> str:
    sc = sidecar(root)
    tiers = [t for t in sc["persistence_order"]]
    rank = {x: i for i, t in enumerate(tiers) for x in t}
    st = law["statement"]
    if law["rule"] == "PAR" and not any(b.get("type") == "Reach" for b in st.get("binders") or []):
        return "code"
    if law["rule"] == "DISCH":
        did = st["claim"]["eq"][0]["disch"]
        _model, sub, tag, cls = did.split(":")
        entries = load(root / "gen" / M / "disch" / "classification.json")["entries"]
        mine = [e for e in entries if e["tag"] == tag and (sub != "blocking" or e["class"] == cls)]
        if not mine:
            return "undecided"
        return min((e["disch_class"] for e in mine), key=lambda c: (rank.get(c, len(tiers)), c))
    return "undecided"


# ------------------------------------------------------------------ the predictions (fixed at the prereg)
FACT_ATTR_BWP = "L_fact_attr_Rollup_commitBatchWithProof_batchBlobVersionedHashes_batchDataStore_submitter"
FACT_ATTR_CS = "L_fact_attr_Rollup_commitState_batchBlobVersionedHashes_batchDataStore_submitter"
CC = ["L_par_cc_BatchCache_createBatchHeaderWithSequencerSetHash_enc_sol_v2", "L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0",
      "L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1"]
UNDO_REFUTED = ["L_undo_pair_Rollup_commitBatch_revertBatch", "L_undo_res_Rollup_revertBatch_batchBlobVersionedHashes",
                "L_undo_res_Rollup_revertBatch_batchDataStore"]
UNDO_BVH = "L_undo_res_Rollup_revertBatch_batchBlobVersionedHashes"
SSVH = list(range(185, 217))

# (sink, persistence, reach class or None, reach kind, cost) per REFUTED law of the base
EXPECTED = {
    FACT_ATTR_BWP: ("economic", "undecided", "onlyOwner", "owner", 5),
    FACT_ATTR_CS: ("economic", "undecided", "onlyOwner", "owner", 5),
    "L_disch_noext_rollup_213_f2e7faf8_onlyActiveSubmitter": ("liveness", "undecided", "onlyChallenger", "mapping", 3),
    "L_disch_noext_rollup_363_e11d8bb2_onlyActiveSubmitter": ("liveness", "undecided", "onlyChallenger", "mapping", 3),
    "L_sort_realize_rollup_363_4a64383b": ("liveness", "undecided", "onlyChallenger", "mapping", 3),
    "L_disch_noext_pausableupgradeable_77_ed0ce816_onlyOwner": ("liveness", "undecided", "onlyOwner", "owner", 2),
    "L_disch_noext_rollup_213_f2e7faf8_onlyOwner": ("liveness", "undecided", "onlyOwner", "owner", 3),
    "L_disch_noext_rollup_363_e11d8bb2_onlyOwner": ("liveness", "undecided", "onlyOwner", "owner", 3),
    "L_undo_pair_Rollup_commitBatch_revertBatch": ("liveness", "undecided", "onlyOwner", "owner", 3),
    UNDO_BVH: ("liveness", "undecided", "onlyOwner", "owner", 3),
    "L_disch_noext_rollup_132_d953872f_onlyOwner": ("liveness", "undecided", "onlyOwner", "owner", 4),
    "L_disch_blk_rollup_363_e11d8bb2_onlyActiveSubmitter": ("liveness", "dischargeable", "onlyChallenger", "mapping", 3),
    CC[0]: ("derivation", "code", None, "undecided", None),
    "L_par_dom_BatchHeaderBytes_validate_ok_load_sol": ("derivation", "code", None, "undecided", None),
    CC[1]: ("derivation", "code", "onlyActiveSubmitter", "call", 1),
    CC[2]: ("derivation", "code", "onlyActiveSubmitter", "call", 1),
    "L_fact_kernel_Rollup_commitBatchWithProof_committedBatches_blobhash": ("derivation", "undecided", "anyone",
                                                                             "anyone", 2),
    "L_fact_kernel_Rollup_commitBatch_committedBatches_blobhash": ("derivation", "undecided", "onlyActiveSubmitter",
                                                                    "call", 2),
    "L_pinit_Rollup_importGenesisBatch_committedBatches_17_9": ("state", "undecided", "onlyOwner", "owner", 2),
    "L_sort_tag_rollup_279_e01ea84a": ("state", "undecided", "onlyOwner", "owner", 3),
    "L_par_dom_ok_batch_RetrieveBlobBytes_ok_blob_RetrieveBlobBytes": ("process", "code", None, "pending", None),
    "L_par_tot_batch_RetrieveBlobBytes": ("process", "code", None, "pending", None),
    "L_par_weak_batch_RetrieveBlobBytes_blob_RetrieveBlobBytes": ("process", "code", None, "pending", None),
    "L_undo_res_Rollup_revertBatch_batchDataStore": ("off-chain", "undecided", "onlyOwner", "owner", 2),
}
ORDER = list(EXPECTED)   # the predicted ranking, first to last
SINK_TIERS = {"economic": 2, "liveness": 10, "derivation": 6, "state": 2, "process": 3, "off-chain": 1}
KINDS = {"value": 87, "bound": 9, "pending": 35, "not_applicable": 5}   # over the base's 136 laws

# whitepaper §11.3: the O-row whose obstruction each law's is, and its Impact (sink / reach / persistence); the sink is
# the first class the column names
IMPACT = {
    "L_par_dom_BatchHeaderBytes_validate_ok_load_sol": ("O1", "derivation", "owner", "until upgrade"),
    "L_par_dom_ok_batch_RetrieveBlobBytes_ok_blob_RetrieveBlobBytes": ("O4", "process", "bonded", "permanent"),
    "L_par_tot_batch_RetrieveBlobBytes": ("O4", "process", "bonded", "permanent"),
    "L_par_weak_batch_RetrieveBlobBytes_blob_RetrieveBlobBytes": ("O4", "process", "bonded", "permanent"),
    "L_pinit_Rollup_importGenesisBatch_committedBatches_17_9": ("O9", "finality", "owner", "permanent"),
    "L_undo_pair_Rollup_commitBatch_revertBatch": ("O11", "liveness", "bonded", "until upgrade"),
    UNDO_BVH: ("O11", "liveness", "bonded", "until upgrade"),
    "L_fact_kernel_Rollup_commitBatch_committedBatches_blobhash": ("O22", "derivation", "bonded", "until upgrade"),
    "L_fact_kernel_Rollup_commitBatchWithProof_committedBatches_blobhash": ("O22", "derivation", "bonded",
                                                                             "until upgrade"),
    FACT_ATTR_BWP: ("O25", "economic", "bonded", "until upgrade"),
    FACT_ATTR_CS: ("O25", "economic", "bonded", "until upgrade"),
    "L_sort_tag_rollup_279_e01ea84a": ("O26", "finality", "bonded", "until upgrade"),
    "L_sort_realize_rollup_363_4a64383b": ("O27", "liveness", "challenger", "until outside action"),
    "L_disch_blk_rollup_363_e11d8bb2_onlyActiveSubmitter": ("O31", "liveness", "challenger", "until outside action"),
    "L_disch_noext_rollup_363_e11d8bb2_onlyActiveSubmitter": ("O31", "liveness", "challenger",
                                                              "until outside action"),
    "L_disch_noext_rollup_363_e11d8bb2_onlyOwner": ("O31", "liveness", "challenger", "until outside action"),
}
REACH_WORDS = {"anyone": "anyone", "onlyActiveSubmitter": "bonded", "onlyChallenger": "challenger",
               "onlyOwner": "owner", "caller_rollup_210": "ProxyAdmin"}
PERSISTENCE_WORDS = {"code": {"until upgrade", "until code change", "permanent"},
                     "non-dischargeable": {"until upgrade", "permanent"},
                     "external-dependent": {"until outside action", "until owner"},
                     "dischargeable": {"transient", "per batch"}}
SINK_DIFFER = {"L_pinit_Rollup_importGenesisBatch_committedBatches_17_9", "L_sort_tag_rollup_279_e01ea84a"}
REACH_MATCH = {"L_pinit_Rollup_importGenesisBatch_committedBatches_17_9",
               "L_fact_kernel_Rollup_commitBatch_committedBatches_blobhash", "L_sort_realize_rollup_363_4a64383b",
               "L_disch_blk_rollup_363_e11d8bb2_onlyActiveSubmitter",
               "L_disch_noext_rollup_363_e11d8bb2_onlyActiveSubmitter"}
PERSISTENCE_MATCH = {"L_par_dom_BatchHeaderBytes_validate_ok_load_sol",
                     "L_par_dom_ok_batch_RetrieveBlobBytes_ok_blob_RetrieveBlobBytes",
                     "L_par_tot_batch_RetrieveBlobBytes", "L_par_weak_batch_RetrieveBlobBytes_blob_RetrieveBlobBytes"}


def compare(entry: dict) -> dict:
    """One ranking entry against its §11.3 row: {sink, reach, persistence: bool}, or {} without an analogue."""
    lid = entry["law_id"]
    if lid not in IMPACT:
        return {}
    _o, sink, reach, pers = IMPACT[lid]
    imp = entry["impact"]
    return {"sink": imp["sink"]["class"] == sink,
            "reach": REACH_WORDS.get(imp["reach"].get("class") or "") == reach,
            "persistence": pers in PERSISTENCE_WORDS.get(imp["persistence"]["class"], set())}
