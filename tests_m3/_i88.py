"""I88's instrument (fixed at the prereg; it imports nothing from holon/): the contract's rules written a second time.

It builds the sidecar's sections (the vocabulary, the hypotheses, the plan-stated statements and the search space) from
the plan and from I85's frozen sidecar, and it recomputes, independently of holon/, everything the contract checks
against the outputs:
  - the generated law files (rule L2): each statement with its refs inserted, and the law's metadata;
  - the product and hypothesis refs (rule L3);
  - the candidate payloads of the search space (rules W1-W2);
  - the observations, from a receiver dump and from a committed header (rule W4): by the field names of the
    vocabulary, and by the header layout's offsets;
  - the split report (rule SP1).

Run once at the prereg to write the sidecar:  python -m tests_m3._i88 --write
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = "spec/M3/lib/derivation_laws.json"
I85_SIDECAR = "spec/M3/lib/derivation.json"
VERSION = "holon-derivation-laws/0.1"


def canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def file_sha256(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def law_text(obj) -> str:
    """A law file's text: holon.rules.dumps's form (indent 2, sorted keys, a final newline)."""
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def out_text(obj) -> str:
    """Every other output's text: canonical JSON with indent 1, sorted keys, a final newline."""
    return json.dumps(obj, indent=1, sort_keys=True) + "\n"


# ====================================================================== the statements (rules S1-S4)
def V(n: str) -> dict:
    return {"var": n}


def P(pid: str, on: list, contexts: dict | None = None) -> dict:
    t = {"product": pid, "on": on}
    if contexts is not None:
        t["contexts"] = contexts
    return t


TRUE = {"bool": True}
BINDERS = [("s", "Reach"), ("x", "Act"), ("p", "List<Nat>"), ("ts", "List<Nat>"), ("cb", "Fn<Bytes,Blobs>"),
           ("pl", "Fn<Blobs,Payload>"), ("vh", "Fn<Blob,Word>"), ("et", "Fn<Txs,Bytes>"), ("dt", "Fn<Bytes,Txs>")]
CONSUMER = ["x", "p", "cb", "pl", "dt"]      # the arguments of a consumer term
DATA = ["x", "p", "cb", "pl"]                # the arguments of txs_data (computed before the decoder is called)
COMMITTED = ["s", "x"]


def binders(extra=()) -> list:
    return [{"q": "forall", "name": n, "type": t} for n, t in list(BINDERS) + list(extra)]


def on(names) -> list:
    return [V(n) for n in names]


def step_premises(action: str) -> list:
    """The product step's premises (rule S2's base): the commit action, its success, the blobs' hashes, the blob layer
    and the codec hypotheses, the decoder's argument as the encoder's image of ts, and the consumer's success."""
    return [
        {"eq": [{"fn": f"is_{action}", "args": [V("x")]}, TRUE]},
        {"eq": [{"fn": "last_ok", "args": [{"step": V("x"), "from": V("s")}]}, TRUE]},
        {"eq": [P("blobs_match", on(["x", "p", "cb", "vh"])), TRUE]},
        {"hyp": {"name": "HypB", "args": on(["cb", "pl"])}},
        {"hyp": {"name": "HypT", "args": on(["et", "dt"])}},
    ]


def consumer_premises(contexts: dict | None = None) -> list:
    return [
        {"eq": [P("txs_data", on(DATA), contexts), {"app": "et", "args": [V("ts")]}]},
        {"eq": [P("derive_ok", on(CONSUMER), contexts), TRUE]},
    ]


def laws(action: str) -> list:
    """The five plan-stated laws (rule S1), in the order the sidecar lists them."""
    out = []
    # O7 (PAR-cycle, F11b,c): the cycle's closing check, the derived last block against the committed one
    out.append({
        "id": "L_prod_cycle_lastBlockNumber", "rule": "PAR", "subform": "product_cycle",
        "maps_to": [{"id": "O7"}, {"id": "F11", "role": "b,c"}],
        "obligation": ("the lastBlockNumber cycle closes: the last block number the consumer derives for a committed "
                       "batch is the LastBlockNumber of the header the commit wrote, which the next batch's "
                       "derivation reads as its parent's"),
        "statement": {"binders": binders(),
                      "assume": step_premises(action) + consumer_premises() + [
                          {"eq": [P("committed_ok:LastBlockNumber", on(COMMITTED)), TRUE]}],
                      "claim": {"eq": [P("derived:lastBlockNumber", on(CONSUMER)),
                                       P("committed:LastBlockNumber", on(COMMITTED))]},
                      "scope": {"kind": "unbounded"}}})
    # F11's L1 count (no O-id: a Question): the committed count against the count the consumer derives
    out.append({
        "id": "L_prod_count_l1MsgNum", "rule": "PAR", "subform": "product_count",
        "maps_to": [{"id": "F11", "role": "L1 count (no O-id)"}],
        "obligation": ("the L1-message count the commit wrote (the header's L1MessagePopped) is the number of L1 "
                       "messages the derived blocks consume (the sum of their l1MsgNum)"),
        "statement": {"binders": binders(),
                      "assume": step_premises(action) + consumer_premises() + [
                          {"eq": [P("committed_ok:L1MessagePopped", on(COMMITTED)), TRUE]}],
                      "claim": {"eq": [P("derived_sum:l1MsgNum", on(CONSUMER)),
                                       P("committed:L1MessagePopped", on(COMMITTED))]},
                      "scope": {"kind": "unbounded"}}})
    # O8 (PAR-consumer, F11a): the law pair under HypC, statements equal but for the hypothesis's name
    for hyp in ("HypC_binds_trailing", "HypC_ignores_trailing"):
        out.append({
            "id": f"L_prod_trailing_{hyp}", "rule": "PAR", "subform": "product_trailing",
            "maps_to": [{"id": "O8"}, {"id": "F11", "role": "a"}],
            "obligation": ("a committed batch the circuit accepts carries no transaction the derivation leaves "
                           "undequeued (trailing payload), under the circuit hypothesis " + hyp),
            "statement": {"binders": binders([("circ", "Fn<Step,Bool>")]),
                          "assume": step_premises(action) + consumer_premises() + [
                              {"eq": [P("circuit_accepts", on(["circ", "s", "x", "p", "cb", "pl", "dt"])), TRUE]},
                              {"hyp": {"name": hyp, "args": on(["circ", "cb", "pl", "vh", "et", "dt"])}}],
                          "claim": {"eq": [P("trailing", on(CONSUMER)), {"nat": 0}]},
                          "scope": {"kind": "unbounded"}}})
    # O24 (FACT, F11f): version-0 calldata contexts, read by the consumer and bound by no commitment
    c1, c2 = V("c1"), V("c2")
    out.append({
        "id": "L_prod_calldata_BlockContexts", "rule": "FACT", "subform": "product_calldata",
        "maps_to": [{"id": "O24"}, {"id": "F11", "role": "f"}],
        "obligation": ("the derivation of a committed version-0 batch is determined by what the commitment binds: "
                       "two calldata block-context arguments, which no commitment binds, derive the same blocks"),
        "statement": {"binders": binders([("c1", "List<Nat>"), ("c2", "List<Nat>")]),
                      "assume": step_premises(action) + [
                          {"eq": [P("input:version", on(["x"])), {"nat": 0}]}] +
                          consumer_premises(c1) + consumer_premises(c2),
                      "claim": {"eq": [P("derived_blocks", on(CONSUMER), c1), P("derived_blocks", on(CONSUMER), c2)]},
                      "scope": {"kind": "unbounded"}}})
    return out


def hypotheses(action: str) -> dict:
    """The stated hypotheses (rule S3): each with its family, parameters, statement and evaluator instance."""
    base = step_premises(action)[:3] + consumer_premises()
    base2 = [{"eq": [{"fn": f"is_{action}", "args": [V("x")]}, TRUE]},
             {"eq": [{"fn": "last_ok", "args": [{"step": V("x"), "from": V("s")}]}, TRUE]},
             {"eq": [P("blobs_match", on(["x", "p2", "cb", "vh"])), TRUE]},
             {"eq": [P("txs_data", on(["x", "p2", "cb", "pl"])), {"app": "et", "args": [V("ts2")]}]},
             {"eq": [P("derive_ok", on(["x", "p2", "cb", "pl", "dt"])), TRUE]}]
    step = [("s", "Reach"), ("x", "Act"), ("p", "List<Nat>"), ("ts", "List<Nat>")]
    return {
        "HypB": {"family": "HypB", "parameters": ["cb", "pl"],
                 "statement": {"binders": [{"q": "forall", "name": "q", "type": "List<Nat>"}],
                               "claim": {"eq": [{"app": "pl", "args": [{"app": "cb", "args": [V("q")]}]},
                                                P("ok_payload", [V("q")])]}},
                 "instance": ("cb is the batch's blob construction: the sidecar's compressor (I85's extract.compressor) "
                              "then canonical packing (I85's rule C2); pl is the consumer's blob layer: the "
                              "retrieval function of vocabulary.blob_layer on each blob, the concatenation, and the "
                              "decompression function of vocabulary.blob_layer, its oracle answered by the real "
                              "library"),
                 "doc": ("the blob layer recovers every payload the blob construction encodes: a stated oracle "
                         "hypothesis (whitepaper §8.5) in HypZ's form, for the retrieval, concatenation and "
                         "decompression the consumer runs before it parses the payload")},
        "HypT": {"family": "HypT", "parameters": ["et", "dt"],
                 "statement": {"binders": [{"q": "forall", "name": "u", "type": "List<Nat>"}],
                               "claim": {"eq": [{"app": "dt", "args": [{"app": "et", "args": [V("u")]}]},
                                                P("ok_txs", [V("u")])]}},
                 "instance": ("et concatenates one encoding per transaction (the search uses copies of "
                              "search.transaction); dt is the transaction-stream decoder of vocabulary.decoder, "
                              "answered by the real library"),
                 "doc": ("the transaction-stream decoder recovers every stream the encoder builds: a stated oracle "
                         "hypothesis for the transaction codec (whitepaper §11.1); a transaction is an opaque unit")},
        "HypC_binds_trailing": {
            "family": "HypC", "parameters": ["circ", "cb", "pl", "vh", "et", "dt"],
            "statement": {"binders": [{"q": "forall", "name": n, "type": t} for n, t in step],
                          "assume": base + [{"eq": [P("circuit_accepts",
                                                      on(["circ", "s", "x", "p", "cb", "pl", "dt"])), TRUE]}],
                          "claim": {"eq": [P("trailing", on(CONSUMER)), {"nat": 0}]}},
            "instance": "circ accepts a step iff its trailing count is 0",
            "doc": ("HypC_v (whitepaper §8.5), the circuit binds trailing payload: it accepts no committed batch "
                    "whose payload carries a transaction the derived blocks leave undequeued")},
        "HypC_ignores_trailing": {
            "family": "HypC", "parameters": ["circ", "cb", "pl", "vh", "et", "dt"],
            "statement": {"binders": [{"q": "forall", "name": n, "type": t} for n, t in
                                      step + [("p2", "List<Nat>"), ("ts2", "List<Nat>")]],
                          "assume": base + base2 + [{"eq": [P("derived_batch", on(CONSUMER)),
                                                            P("derived_batch", on(["x", "p2", "cb", "pl", "dt"]))]}],
                          "claim": {"eq": [P("circuit_accepts", on(["circ", "s", "x", "p", "cb", "pl", "dt"])),
                                           P("circuit_accepts", on(["circ", "s", "x", "p2", "cb", "pl", "dt"]))]}},
            "instance": "circ accepts every step",
            "doc": ("HypC_v (whitepaper §8.5), the circuit ignores trailing payload: two steps of one commit whose "
                    "derived batches are equal are accepted alike, so what the derivation ignores the circuit "
                    "ignores")},
    }


def vocabulary() -> dict:
    """The target vocabulary of the product terms (rule S2); holon/derivation/laws.py reads every name from here."""
    return {
        "header_type": "morph-l2/common/batch.BatchHeaderBytes",
        "header_component": "gen/M3/codec/header_length.json",
        "header_getter": "BatchHeaderBytes_{}",
        "blocks_field": "blockContexts",
        "block_number": "Number",
        "dequeue": ["txsNum", "l1MsgNum"],
        "contexts_field": "BlockContexts",
        "decoder": "morph-l2/common/batch.DecodeTxsFromBytes",
        "blob_layer": {"retrieve": "morph-l2/common/batch.RetrieveBlobBytes",
                       "decompress": "morph-l2/common/codec/zstd.DecompressBatchBytes"},
        "version_member": "version",
        "terms": {
            "derive_ok": "Bool: the consumer's entry, run on the step's batch, returns a nil error (no error, no panic)",
            "derived:<F>": "Nat: the receiver's field F once the entry returns",
            "derived_sum:<f>": "Nat: the sum over the receiver's blocks_field of each element's field f",
            "derived_blocks": "List<Nat>: the block_number field of each element of the receiver's blocks_field",
            "derived_batch": "the receiver's whole value once the entry returns",
            "trailing": ("Nat: the length of dt's answer on txs_data less the sum over the receiver's blocks_field of "
                         "dequeue[0] - dequeue[1]"),
            "txs_data": "List<Nat>: the argument of the entry's call of the decoder (empty when the entry returns before)",
            "committed_ok:<G>": ("Bool: the commit step of x from s succeeds and the getter G of header_type returns "
                                 "a nil error on the committed header (the argument of the keccak256 the step writes "
                                 "to I85's header family, rule J3), as the function header_getter.format(G) of the "
                                 "linked header component header_component (holon.gen.linked's compiled model) "
                                 "answers it: Some"),
            "committed:<G>": "Nat: that getter's bytes, big-endian",
            "input:<m>": "Nat: the member m of x's commit parameter",
            "blobs_match": "Bool: x's blob hashes (blobhash(i)) are vh of cb(p)'s blobs in order, then zero",
            "circuit_accepts": "Bool: circ applied to the step's statement (the committed header and the blobs cb(p))",
            "ok_payload": "the blob layer's success answer carrying its argument's bytes",
            "ok_txs": "the decoder's success answer carrying its argument's transactions",
        },
    }


# ====================================================================== the search space (rules W1-W2)
def _ctx_fields(ctx: bytes) -> dict:
    return {"number": int.from_bytes(ctx[0:8], "big"), "timestamp": int.from_bytes(ctx[8:16], "big"),
            "baseFee": "0x" + ctx[16:48].hex(), "gasLimit": int.from_bytes(ctx[48:56], "big"),
            "txsNum": int.from_bytes(ctx[56:58], "big"), "l1MsgNum": int.from_bytes(ctx[58:60], "big")}


def _rlp_len(b: bytes, i: int) -> int:
    """The length of the RLP item at b[i:] (header included)."""
    x = b[i]
    if x < 0x80:
        return 1
    if x < 0xb8:
        return 1 + (x - 0x80)
    if x < 0xc0:
        n = x - 0xb7
        return 1 + n + int.from_bytes(b[i + 1:i + 1 + n], "big")
    if x < 0xf8:
        return 1 + (x - 0xc0)
    n = x - 0xf7
    return 1 + n + int.from_bytes(b[i + 1:i + 1 + n], "big")


def first_transaction(stream: bytes) -> bytes:
    """The first transaction of a stream: a type byte (1..0x7f) then one RLP item, or a legacy RLP list."""
    if stream[0] < 0x80:
        return stream[:1 + _rlp_len(stream, 1)]
    return stream[:_rlp_len(stream, 0)]


def count_transactions(stream: bytes) -> int:
    """The number of transactions in a stream (a zero type byte or the end stops it)."""
    i, n = 0, 0
    while i < len(stream) and stream[i] != 0:
        i += (1 + _rlp_len(stream, i + 1)) if stream[i] < 0x80 else _rlp_len(stream, i)
        n += 1
    return n


def search(root: Path = ROOT) -> dict:
    """The search space (rule W1): its template context and transaction come from I85's first product payload."""
    i85 = load(root / I85_SIDECAR)
    raw = bytes.fromhex(i85["corpus"]["product"][0]["commits"][0]["payload"]["raw"][0][2:])
    ctx = _ctx_fields(raw[:60])
    return {
        "steps": ("every commit of the product traces (I85's corpus.product), in trace order then commit order, "
                  "from the state and parent header its trace reaches (I85's rules K1-K3)"),
        "blocks": [1, 2],
        "mutations": ["consistent", "last_number", "l1_count", "trailing"],
        "pairs": [["calldata", "calldata_last_number"]],
        "context": {"layout": [["number", 8], ["timestamp", 8], ["baseFee", 32], ["gasLimit", 8],
                               ["txsNum", 2], ["l1MsgNum", 2]],
                    "timestamp": ctx["timestamp"], "baseFee": ctx["baseFee"], "gasLimit": ctx["gasLimit"]},
        "transaction": "0x" + first_transaction(raw[60:]).hex(),
        "start": "the parent header's LastBlockNumber getter plus 1 when it returns a nil error, else 1",
    }


def context_bytes(sp: dict, number: int, txs: int, l1: int) -> bytes:
    c = sp["context"]
    vals = {"number": number, "timestamp": c["timestamp"], "baseFee": int(c["baseFee"], 16), "gasLimit": c["gasLimit"],
            "txsNum": txs, "l1MsgNum": l1}
    return b"".join(int(vals[name]).to_bytes(w, "big") for name, w in c["layout"])


def payload(sp: dict, start: int, n: int, mutation: str) -> tuple:
    """(payload bytes, calldata contexts bytes or None) of a candidate (rule W1's mutations)."""
    nums = list(range(start, start + n))
    pairs = [(0, 0)] * n
    stream = b""
    if mutation in ("last_number", "calldata_last_number"):
        nums[-1] += 1
    if mutation == "l1_count":
        pairs[0] = (1, 1)
    if mutation == "trailing" or mutation.startswith("calldata"):
        stream = bytes.fromhex(sp["transaction"][2:])
    ctxs = b"".join(context_bytes(sp, k, a, b) for k, (a, b) in zip(nums, pairs))
    if mutation.startswith("calldata"):
        return stream, n.to_bytes(2, "big") + ctxs
    return ctxs + stream, None


# ====================================================================== refs and the law files (rules L2-L3)
def product_ref(root: Path, side: dict) -> str:
    ins = side["inputs"]
    doc = {"template": "holon.derivation.laws/product", "template_version": 1,
           "document": file_sha256(root / ins["document"]), "join": load(root / ins["product"])["join"],
           "deployment": file_sha256(root / ins["deployment"]),
           "header_component": file_sha256(root / side["vocabulary"]["header_component"]),
           "vocabulary": side["vocabulary"]}
    return "sha256:" + sha256_bytes(canon(doc))


def hyp_ref(side: dict, name: str) -> str:
    h = {k: v for k, v in side["hypotheses"][name].items() if k not in ("doc", "instance")}
    return "sha256:" + sha256_bytes(canon({"template": "holon.derivation.laws/hypothesis", "template_version": 1,
                                           "name": name, "hypothesis": h}))


def with_refs(t, pref: str, side: dict):
    if isinstance(t, list):
        return [with_refs(x, pref, side) for x in t]
    if not isinstance(t, dict):
        return t
    out = {k: with_refs(v, pref, side) for k, v in t.items()}
    if isinstance(t.get("product"), str):
        out["ref"] = pref
    if isinstance(t.get("hyp"), dict):
        out["hyp"] = dict(out["hyp"], ref=hyp_ref(side, t["hyp"]["name"]))
    return out


def expected_law(entry: dict, root: Path, side: dict) -> dict:
    ls = side["law_set"]
    return {"ir_version": ls["ir_version"], "law_id": entry["id"], "milestone": ls["milestone"],
            "rule": entry["rule"], "subform": entry["subform"], "rule_catalog_version": ls["rule_catalog_version"],
            "facts": ls["facts"], "facts_sha256": file_sha256(root / ls["facts"]),
            "statement": with_refs(entry["statement"], product_ref(root, side), side),
            "maps_to": entry["maps_to"],
            "notes": (f"plan-stated product law ({SIDECAR}, {entry['id']}): {entry['obligation']}; generated by "
                      "holon derivation laws")}


def hyp_names(law: dict) -> list:
    return [p["hyp"]["name"] for p in law["statement"].get("assume", []) if isinstance(p.get("hyp"), dict)]


def splits(laws_: list, statuses: dict, side: dict) -> dict:
    """SP1: law pairs on family F: laws naming different hypotheses of F whose statements are equal once every hyp
    premise of F is renamed F (and its ref dropped); split iff some law of the pair is PROVED and some REFUTED."""
    fam = {h: e["family"] for h, e in side["hypotheses"].items()}
    groups: dict = {}
    for law in laws_:
        mine: dict = {}
        for h in hyp_names(law):
            mine.setdefault(fam[h], []).append(h)
        for f, hs in mine.items():
            if len(set(hs)) != 1:
                continue
            st = copy.deepcopy(law["statement"])
            for p in st.get("assume", []):
                if isinstance(p.get("hyp"), dict) and p["hyp"]["name"] in hs:
                    p["hyp"] = {k: v for k, v in p["hyp"].items() if k != "ref"}
                    p["hyp"]["name"] = f
            groups.setdefault((f, canon(st)), {})[law["law_id"]] = hs[0]
    pairs = []
    for (f, _), members in groups.items():
        if len(set(members.values())) < 2:
            continue
        out = {lid: {"hypothesis": h, "status": statuses.get(lid, "UNKNOWN")} for lid, h in sorted(members.items())}
        st = {x["status"] for x in out.values()}
        pairs.append({"family": f, "laws": out, "split": "PROVED" in st and "REFUTED" in st})
    pairs.sort(key=lambda y: (y["family"], sorted(y["laws"])))
    return {"splits_version": "holon-splits/0.1", "milestone": side["law_set"]["milestone"], "pairs": pairs}


# ====================================================================== observations (rule W4)
HEADER_OFFSETS = {"Version": (0, 1), "BatchIndex": (1, 9), "L1MessagePopped": (9, 17),
                  "TotalL1MessagePopped": (17, 25), "LastBlockNumber": (249, 257)}


def header_getter(header: bytes, name: str):
    """A committed header's field by the header layout (whitepaper App. C; M0 facts): None when the getter errs (a
    version-0 header has no LastBlockNumber; a header shorter than its version's length)."""
    if not header:
        return None
    want = 249 if header[0] == 0 else 257
    if len(header) != want or header[0] > 2 or (name == "LastBlockNumber" and header[0] == 0):
        return None
    a, b = HEADER_OFFSETS[name]
    return int.from_bytes(header[a:b], "big")


def _num(v):
    return int(v) if isinstance(v, (int, str)) else None


def derived_value(info: dict, term: str, voc: dict, decoded: int | None = None):
    """The value of a consumer term from a receiver dump (I85's rule G5 dump)."""
    blocks = info.get(voc["blocks_field"]) or []
    if term.startswith("derived:"):
        return _num(info.get(term.split(":", 1)[1]))
    if term.startswith("derived_sum:"):
        f = term.split(":", 1)[1]
        return sum(int(b.get(f)) for b in blocks)
    if term == "derived_blocks":
        return [int(b.get(voc["block_number"])) for b in blocks]
    if term == "trailing":
        a, b = voc["dequeue"]
        return None if decoded is None else decoded - sum(int(x.get(a)) - int(x.get(b)) for x in blocks)
    raise KeyError(term)


def write() -> None:
    i85 = load(ROOT / I85_SIDECAR)
    action = i85["product"]["commit_action"]
    side = {
        "derivation_laws_version": VERSION,
        "doc": ("I88 (= I39b) sidecar, fixed at the I88 prereg (contract: the docstring of "
                "tests_m3/test_derivation_laws.py; written by tests_m3/_i88.py --write). The five plan-stated laws over "
                "I85's product machine (whitepaper §11.3's rows O7, O8 and O24, and F11's L1 count), their stated "
                "hypotheses, the target vocabulary of the product terms and the bounded search space of the "
                "evaluator-level witness search. It is the only place the target's names live for "
                "holon/derivation/laws.py. It states no outcome."),
        "inputs": {"product_sidecar": I85_SIDECAR, "document": i85["extract"]["output"],
                   "rollup_document": i85["product"]["rollup_document"],
                   "product": "gen/M3/derivation/product.json", "corpus": "gen/M3/derivation/corpus.json",
                   "deployment": i85["product"]["deployment"]["record"],
                   "header_component": vocabulary()["header_component"]},
        "law_set": {"laws": "laws/M3/derivation", "records": "results/M3/derivation/laws", "milestone": "M3",
                    "facts": i85["product"]["rollup_document"], "ir_version": "holon-ir/0.3",
                    "rule_catalog_version": "holon-rules/0.1"},
        "outputs": {"candidates": "gen/M3/derivation/laws/candidates.json",
                    "environment": "gen/M3/derivation/laws/environment.json",
                    "evaluations": "results/M3/derivation/laws/evaluations.json",
                    "splits": "results/M3/derivation/splits.json",
                    "replay": "replay/M3/derivation/laws.json"},
        "vocabulary": vocabulary(),
        "hypotheses": hypotheses(action),
        "laws": laws(action),
        "search": search(ROOT),
    }
    (ROOT / SIDECAR).write_text(out_text(side), encoding="utf-8")
    print(f"wrote {SIDECAR}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        write()
    else:
        print(__doc__)
