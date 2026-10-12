"""replay.py — S6: replay historical Morph mainnet commits through the COMPILED
generated model (whitepaper §8.7, M2_SPEC §3 row S6).

Never a hand reimplementation: header decode/encode, batch hash, blob
versioned-hash and the commitBatch transition run on the compiled
gen/M0 + gen/M1 artifacts via replay_driver.mjs. Concrete on-chain values are
translated to model atoms by ONE AtomMap; every disagreement is classified
extraction defect / real defect / oracle mismatch.

Inputs (the §4 corpus format):
  manifest.json: {chain, rollup_proxy, window, commits:[{batch_index, tx, block,
    method, calldata_sha256, blob_versioned_hashes, blobs_sha256,
    post:{committedBatches, committedStateRoots, lastCommittedBatchIndex}}]}
  payloads resolved by sha256 from --cache ($HOLON_CACHE, raw files) or
  --payload-dir (fixture *.json {"data":"0x.."}).
  per-commit reconstruction records under --records/commits/<batch_index>.json
  (see replay_fixture.py for the shape; the full-corpus fetcher S5 emits the
  same record format).

Output: replay/M2/report.json (deterministic; no timestamps).

CLI:
  python -m holon.hist.replay --manifest replay/M2/corpus/fixtures/manifest.json \
      --records replay/M2/corpus/fixtures --payload-dir replay/M2/corpus/fixtures/payload \
      --out replay/M2/report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .replay_atoms import AtomMap, canon_b32, canon_addr, ZERO32, ZERO_VH
from .replay_model import (ModelSession, hdr_cells, fields_named, b2h, h2b,
                           be_int)

REPO = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------- selectors
SEL_COMMIT_BATCH = "41f756da"
SEL_COMMIT_STATE = "67caa37a"
SEL_COMMIT_WITH_PROOF = "2a58a723"
METHOD_BY_SELECTOR = {
    SEL_COMMIT_BATCH: "commitBatch",
    SEL_COMMIT_STATE: "commitState",
    SEL_COMMIT_WITH_PROOF: "commitBatchWithProof",
}

# older implementations that still emit CommitBatch: 2-arg overload
# commitBatch(BatchDataInput, BatchSignatureInput) (v1/v2 era) and the v0-era
# commitBatch. Same BatchDataInput layout; the extra signature arg is an
# oracle-side detail the model does not cover -> coverage debt.
METHOD_BY_SELECTOR["428868b5"] = "commitBatch"
METHOD_BY_SELECTOR["d63b3549"] = "commitBatch"
OLD_SELECTORS = {"428868b5", "d63b3549"}

REASONS = {  # facts["reasons"]: model revert code -> contract revert string
    1: "only active submitter allowed", 2: "pending revert request",
    3: "Pausable: paused", 4: "commitBatch requires no stored blob hash",
    5: "l1msg delay", 6: "V2 requires at least 1 blob",
    7: "legacy batches support exactly 1 blob", 8: "invalid version",
    9: "previous state root is zero", 10: "new state root is zero",
    11: "batch already committed", 12: "incorrect batch index",
    14: "incorrect previous state root", 15: "message index out of range",
    16: "panic:0x11",
}


# ---------------------------------------------------------------- calldata
def decode_commit_input(method: str, data: bytes) -> dict:
    """ABI-decode the BatchDataInput tuple (plus method-specific extras)."""
    body = data[4:]
    if method in ("commitBatch", "commitState"):
        head = body
    elif method == "commitBatchWithProof":
        head = body  # tuple + _batchHeader + _batchProof heads follow
    else:
        raise ValueError(f"unknown method {method}")
    if len(head) < 8 * 32:
        raise ValueError("calldata too short for BatchDataInput")
    base = int.from_bytes(head[:32], "big")  # top-level tuple arg offset
    t = head[base:]
    w = [int.from_bytes(t[32 * i:32 * i + 32], "big") for i in range(7)]
    (version, hdr_off, last_block_number, num_l1_messages,
     prev_state_root, post_state_root, withdrawal_root) = w
    parent_hdr = b""
    if hdr_off + 32 <= len(t):
        n = int.from_bytes(t[hdr_off:hdr_off + 32], "big")
        parent_hdr = t[hdr_off + 32:hdr_off + 32 + n]
    out = {
        "version": version, "parentBatchHeader": parent_hdr,
        "lastBlockNumber": last_block_number, "numL1Messages": num_l1_messages,
        "prevStateRoot": "0x" + prev_state_root.to_bytes(32, "big").hex(),
        "postStateRoot": "0x" + post_state_root.to_bytes(32, "big").hex(),
        "withdrawalRoot": "0x" + withdrawal_root.to_bytes(32, "big").hex(),
    }
    if method == "commitBatchWithProof" and len(body) >= 9 * 32:
        off_h = int.from_bytes(body[7 * 32:8 * 32], "big")
        off_p = int.from_bytes(body[8 * 32:9 * 32], "big")
        if off_h + 32 <= len(body):
            n = int.from_bytes(body[off_h:off_h + 32], "big")
            out["batchHeaderArg"] = body[off_h + 32:off_h + 32 + n]
        if off_p + 32 <= len(body):
            n = int.from_bytes(body[off_p:off_p + 32], "big")
            out["batchProof"] = body[off_p + 32:off_p + 32 + n]
    return out


# ---------------------------------------------------------------- payloads
class PayloadStore:
    def __init__(self, cache_dir: Path | None, payload_dir: Path | None):
        self.cache_dir = cache_dir
        self.payload_dir = payload_dir

    def resolve(self, sha256: str) -> bytes:
        sha = sha256[2:] if sha256.startswith("0x") else sha256
        if self.payload_dir:
            for cand in (self.payload_dir / f"{sha}.json",
                         self.payload_dir / sha):
                if cand.exists():
                    if cand.suffix == ".json":
                        obj = json.loads(cand.read_text())
                        return h2b(obj["data"])
                    return bytes.fromhex(cand.read_text().strip())
        if self.cache_dir:
            cand = self.cache_dir / sha
            if cand.exists():
                raw = cand.read_bytes()
                try:
                    s = raw.decode().strip()
                    if s.startswith("{"):
                        return h2b(json.loads(s)["data"])
                    return h2b(s)
                except UnicodeDecodeError:
                    return raw
        raise FileNotFoundError(f"payload {sha} not found in payload dir or cache")


# ---------------------------------------------------------------- check acc
class Checks:
    """Accumulates per-check results and classifies disagreements."""

    CATEGORIES = ("agree", "extraction_defect", "real_defect", "oracle_mismatch",
                  "coverage_debt")

    def __init__(self):
        self.items = []

    def add(self, name: str, expected, got, verdict: str, detail: str = "",
            rule: str | None = None, evidence=None, **extra):
        item = {"check": name, "verdict": verdict}
        if expected is not None:
            item["expected"] = expected
        if got is not None:
            item["got"] = got
        if detail:
            item["detail"] = detail
        # §8.7+: every disagreement needs an explicit named rule plus the
        # concrete evidence that matched it; a disagreement no named rule
        # explains is `unexplained` (never auto-classified by mechanism).
        if verdict not in ("agree", "coverage_debt"):
            if rule:
                item["rule"] = rule
                if evidence is not None:
                    item["evidence"] = evidence
            else:
                item["unexplained"] = True
        item.update(extra)
        self.items.append(item)
        return verdict

    def agree(self, name, expected=None, got=None, detail=""):
        return self.add(name, expected, got, "agree", detail)

    def disagree(self, name, cls, expected, got, detail="", rule=None,
                 evidence=None):
        return self.add(name, expected, got, cls, detail, rule=rule,
                        evidence=evidence)


# ---------------------------------------------------------------- engine
class Replay:
    def __init__(self, ms: ModelSession, atoms: AtomMap):
        self.ms = ms
        self.atoms = atoms

    # -- model calls --
    def m_ok_sol(self, b: bytes):
        return self.ms.hdr("ok_sol", b)

    def m_ok_go(self, b: bytes):
        return self.ms.hdr("ok_go", b)

    def m_dec_go(self, b: bytes):
        r = self.ms.hdr("dec_go", b)
        return fields_named(r["$some"]) if isinstance(r, dict) and "$some" in r else None

    def m_enc(self, fn: str, fields: dict[str, list[int]]):
        return self.ms.hdr(fn, hdr_cells(fields))

    def machine(self, fn: str, *args):
        return self.ms.mach(fn, *args)

    # -- concrete oracle formulas (contract semantics, oracle side only) --
    def oracle_bvh(self, version: int, blob_hashes: list[str]) -> str:
        """What the CONTRACT stores as batchBlobVersionedHashes[idx]."""
        if version == 2:
            return self.ms.keccak(b"".join(h2b(canon_b32(h)) for h in blob_hashes))
        # legacy: blobhash(0) or ZERO_VERSIONED_HASH when absent
        return canon_b32(blob_hashes[0]) if blob_hashes else ZERO_VH

    def oracle_prt(self, inch: bool, W: int, cstart: int, t: int) -> int:
        return (W + cstart - t) if inch else 0

    # -- window/entry reconstruction --
    def entry_to_bend(self, e: dict) -> dict:
        return {"$": "HEntry", "ver": e["ver"], "tot": e["tot"], "n": e["n"],
                "hb": e["bvh"], "prev": e["prev"], "post": e["post"],
                "lbn": e["lbn"], "csr": e["csr"], "bvh": e["bvh"],
                "tag": e["tag"], "bdo": e["bdo"], "bdf": e["bdf"],
                "bdn": e["bdn"], "bds": e["bds"]}

    def ch_to_bend(self, c: dict) -> dict:
        return {"$": "HCh", "c": c["c"], "d": c["d"], "s": c["s"],
                "w": c["w"], "f": c["f"]}

    def bd_to_bend(self, b: dict) -> dict:
        return {"$": "HBD", "o": b["o"], "f": b["f"], "n": b["n"], "s": b["s"]}

    def pre_state(self, pre: dict) -> dict:
        """Reconstruction record (concrete values) -> HSt JSON (atom-mapped)."""
        atoms = self.atoms
        win = []
        for e in pre["window"]["entries"]:
            bvh_a = atoms.atom(e["bvh"])
            win.append({"$": "HEntry", "ver": e["ver"], "tot": e["tot"],
                        "n": e["n"], "hb": bvh_a,
                        "prev": atoms.atom(e["prev"]),
                        "post": atoms.atom(e["post"]), "lbn": e["lbn"],
                        "csr": atoms.atom(e["csr"]), "bvh": bvh_a,
                        "tag": 2 if e["ver"] == 2 else 1,
                        "bdo": e["bdo"], "bdf": e["bdf"], "bdn": e["bdn"],
                        "bds": atoms.atom(canon_addr(e["bds"]))})
        sc = pre["scalars"]
        # chs is indexed by batch index; dense-pad to bc with empty_ch
        chs = []
        real = {c["index"]: c for c in pre["challenges"]}
        for i in range(sc["bc"] + 1):
            c = real.get(i)
            if c is None:
                chs.append({"$": "HCh", "c": 0, "d": 0, "s": 0,
                            "w": False, "f": False})
            else:
                chs.append({"$": "HCh",
                            "c": atoms.atom(canon_addr(c["challenger"])),
                            "d": c["challengeDeposit"], "s": c["startTime"],
                            "w": c["challengeSuccess"], "f": c["finished"]})
        return {"$": "HSt",
                "t": pre["t"], "lfi": sc["lfi"], "inch": sc["inch"],
                "bc": sc["bc"], "rri": sc["rri"], "paused": sc["paused"],
                "W": sc["W"], "F": sc["F"], "D": sc["D"],
                "qlen": pre["queue"]["qlen"], "qpend": pre["queue"]["qpend"],
                "enq": pre["queue"]["enq"],
                "active": [atoms.atom(canon_addr(a))
                           for a in pre["active_submitters"]],
                "chals": [], "fsr": [], "chs": chs, "win": win,
                "s_csr": [atoms.atom(v) for v in pre["residues"]["csr"]],
                "s_bd": [{"$": "HBD", "o": b["o"], "f": b["f"], "n": b["n"],
                          "s": atoms.atom(canon_addr(b["s"]))}
                         for b in pre["residues"]["bd"]],
                "s_bvh": [atoms.atom(v) for v in pre["residues"]["bvh"]],
                "s_tag": pre["residues"]["tag"],
                "log": []}

    # -- one commit --
    def replay_commit(self, c: dict, rec: dict, calldata: bytes,
                      successor_parent: bytes | None) -> dict:
        """Replay one commit record; return the per-commit report row."""
        checks = Checks()
        idx = c["batch_index"]
        method = c.get("method") or METHOD_BY_SELECTOR.get(calldata[:4].hex(), "?")
        coverage = []
        sel_hex = c.get("selector") or calldata[:4].hex()
        sel_hex = sel_hex[2:] if sel_hex.startswith("0x") else sel_hex
        if sel_hex in OLD_SELECTORS:
            coverage.append({
                "element": "Rollup.sol external interface",
                "kind": "old_selector",
                "reason": f"selector 0x{sel_hex} is a legacy "
                          "commitBatch(BatchDataInput,BatchSignatureInput) "
                          "overload; the BatchSignatureInput arg (whitelister "
                          "signature check) is outside the model"})
        res = {"batch_index": idx, "tx": c["tx"], "block": c["block"],
               "method": method, "checks": checks.items}
        try:
            inp = decode_commit_input(method, calldata)
        except Exception as e:
            checks.disagree("decode_calldata", "oracle_mismatch", "decodable", repr(e))
            res["verdict"] = "oracle_mismatch"
            return res
        parent_hdr = inp["parentBatchHeader"]
        ver_new = inp["version"]
        ver_parent = parent_hdr[0] if parent_hdr else None
        pre = rec["pre"]
        post = dict(c.get("post") or {})
        post.update(rec.get("post") or {})
        parent_idx = idx - 1
        res["input"] = {
            "version": ver_new, "parent_header_len": len(parent_hdr),
            "parent_version": ver_parent, "numL1Messages": inp["numL1Messages"],
            "lastBlockNumber": inp["lastBlockNumber"],
            "prevStateRoot": inp["prevStateRoot"],
            "postStateRoot": inp["postStateRoot"],
            "withdrawalRoot": inp["withdrawalRoot"],
        }

        # ---------- edge 1: header decode/encode ----------
        if not parent_hdr:
            checks.disagree("parent_header_present", "oracle_mismatch",
                            "non-empty", len(parent_hdr))
            res["verdict"] = "oracle_mismatch"
            return res
        ok_sol = self.m_ok_sol(parent_hdr)
        ok_go = self.m_ok_go(parent_hdr)
        dec = self.m_dec_go(parent_hdr)
        checks.add("ok_sol", True if ver_parent in (0, 1, 2) else False, ok_sol,
                   "agree" if ok_sol == (ver_parent in (0, 1, 2)) else
                   "extraction_defect",
                   f"parent version={ver_parent} len={len(parent_hdr)}")
        checks.add("ok_go", ok_sol, ok_go,
                   "agree" if ok_go == ok_sol else "extraction_defect")
        if dec is None:
            checks.disagree("dec_go", "Some(fields)", "None",
                            "extraction_defect")
            res["verdict"] = "extraction_defect"
            return res
        # decoded-field cross checks against chain + calldata
        dver = be_int(dec["version"])
        didx = be_int(dec["batchIndex"])
        checks.add("dec.version", ver_parent, dver,
                   "agree" if dver == ver_parent else "extraction_defect")
        checks.add("dec.batchIndex", parent_idx, didx,
                   "agree" if didx == parent_idx else "real_defect",
                   "presented parent index vs calldata batch index")
        checks.add("dec.postStateHash", canon_b32(inp["prevStateRoot"]),
                   b2h(dec["postStateHash"]),
                   "agree" if b2h(dec["postStateHash"]) ==
                   canon_b32(inp["prevStateRoot"]) else "real_defect",
                   "parent.postStateHash must equal input.prevStateRoot")
        if "lastBlockNumber" in dec:
            dlbn = be_int(dec["lastBlockNumber"])
        else:
            dlbn = None
        self._field_cross(checks, dec, pre, parent_idx)
        # encode roundtrip: build the Hdr from decoded fields, re-encode
        dec_all = dict(dec)
        if "lastBlockNumber" not in dec_all:
            dec_all["lastBlockNumber"] = [0] * 8
        enc_sol = self.m_enc("enc_sol", dec_all)
        sol_cmp = bytes(enc_sol[:len(parent_hdr)]) == parent_hdr
        checks.add("enc_sol_roundtrip", b2h(parent_hdr[:16]) + "...",
                   b2h(enc_sol[:16]) + "...",
                   "agree" if sol_cmp else "extraction_defect",
                   f"len {len(enc_sol)} vs {len(parent_hdr)}")
        if ver_parent == 0:
            enc_go = self.m_enc("enc_go_v0", dec_all)
            checks.add("enc_go_v0_roundtrip", len(parent_hdr), len(enc_go),
                       "agree" if bytes(enc_go) == parent_hdr
                       else "extraction_defect")
        elif ver_parent in (1, 2):
            enc_go = self.m_enc("enc_go_v1", dec_all)
            if ver_parent == 1:
                same = bytes(enc_go) == parent_hdr
                checks.add("enc_go_v1_roundtrip", b2h(parent_hdr[:2]),
                           b2h(enc_go[:2]),
                           "agree" if same else "extraction_defect")
            else:
                # v2: no enc_go_v2 in the model; Go emits v1-bytes patched at [0].
                tail_same = bytes(enc_go[1:]) == parent_hdr[1:]
                checks.add("enc_go_v1_tail_eq", "v2 tail", "v1 tail",
                           "agree" if tail_same else "extraction_defect",
                           "enc_go_v1 always writes version byte 1; "
                           "Go v2 = v1 bytes with h[0]:=2 patch — "
                           "encoder absent from model")
                coverage.append({
                    "element": "facts/morph_header.json encoders",
                    "kind": "missing_encoder",
                    "reason": "no enc_go_v2: Go derives v2 bytes via "
                              "V1.Bytes()+h[0]=2 patch; compared tail only"})

        # ---------- edge 2: batch hash ----------
        kh = self.ms.keccak(parent_hdr)
        stored_parent = pre["committedBatches"][str(parent_idx)]
        checks.add("parent_batch_hash", stored_parent, kh,
                   "agree" if canon_b32(stored_parent) == canon_b32(kh)
                   else "real_defect",
                   "keccak(presented parent header) vs "
                   "committedBatches[parent] at pre-state")

        # ---------- edge 3: blob versioned hash ----------
        # The model abstracts keccak: d_blob_hash(v2, blobs) = 1000+b_enc(blobs)
        # is a *symbolic* atom, so the correct checks are (a) the concrete
        # stored value vs the concrete contract formula, and (b) model-internal
        # consistency (entry.bvh == entry.hb == d_blob_hash output). For legacy
        # versions the model bvh IS the concrete blobhash(0) atom and can be
        # compared concretely.
        bvhs = [canon_b32(h) for h in c.get("blob_versioned_hashes", [])]
        computed_bvh = self.oracle_bvh(ver_new, bvhs)
        stored_bvh = canon_b32(post.get("batchBlobVersionedHash", ZERO32))
        # v2 feeds commit-LOCAL atoms (model_blob_atoms): the aggregate is
        # symbolic and only compared inside this commit, so the relabel is
        # sound and keeps b_enc inside Bend's 2^48 immediate. Legacy versions
        # keep the global atoms (bvh IS the concrete atom, compared below).
        blob_atoms = self.atoms.model_blob_atoms(ver_new, bvhs)
        if ver_new == 2 and bvhs:
            # audit trail for the local relabel: concrete hash -> local atom
            res["blob_atom_map"] = {h: i + 2
                                    for i, h in enumerate(dict.fromkeys(bvhs))}
        model_bvh_atom = self.machine("d_blob_hash", ver_new, blob_atoms)
        checks.add("bvh_stored_vs_contract", computed_bvh, stored_bvh,
                   "agree" if stored_bvh == computed_bvh else "real_defect",
                   "stored batchBlobVersionedHashes[idx] vs "
                   "contract formula (v2: keccak(concat blobhashes), "
                   "legacy: blobhash(0)||Z)")
        if ver_new != 2:
            concrete_bvh_atom = self.atoms.atom(computed_bvh)
            checks.add("bvh_model_atom_vs_concrete", concrete_bvh_atom,
                       model_bvh_atom,
                       "agree" if model_bvh_atom == concrete_bvh_atom
                       else "extraction_defect",
                       f"d_blob_hash({ver_new}, {len(blob_atoms)} blobs)")

        # ---------- edge 4: transition ----------
        blobs_for_model = blob_atoms  # already model atoms (local for v2)
        state = self.pre_state(pre)
        who = self.atoms.atom(canon_addr(rec["from"]))
        parent_atom = parent_idx
        n, lbn = inp["numL1Messages"], inp["lastBlockNumber"]
        prev_a = self.atoms.atom(inp["prevStateRoot"])
        post_a = self.atoms.atom(inp["postStateRoot"])
        if method == "commitBatch":
            dec_dec = self.machine("decide_commitBatch", *self._st_args(state),
                                   who, ver_new, parent_atom, n, lbn, prev_a,
                                   post_a, blobs_for_model)
            st2 = self.machine("step_commitBatch", state, who, ver_new,
                               parent_atom, n, lbn, prev_a, post_a,
                               blobs_for_model)
        elif method == "commitState":
            dec_dec = self.machine("decide_commitState", *self._st_args(state, tags=True),
                                   who, ver_new, parent_atom, n, lbn, prev_a,
                                   post_a, blobs_for_model)
            st2 = self.machine("step_commitState", state, who, ver_new,
                               parent_atom, n, lbn, prev_a, post_a,
                               blobs_for_model)
        elif method == "commitBatchWithProof":
            proof_a = self.atoms.atom("0x" + (inp.get("batchProof") or b"").hex()
                                    or ZERO32)
            dec_dec = self.machine("decide_commitBatchWithProof",
                                   *self._st_args(state, tags=True),
                                   who, ver_new, parent_atom, n, lbn, prev_a,
                                   post_a, blobs_for_model, proof_a)
            st2 = self.machine("step_commitBatchWithProof", state, who, ver_new,
                               parent_atom, n, lbn, prev_a, post_a,
                               blobs_for_model, proof_a)
        else:
            checks.disagree("method_routed", "coverage_debt",
                            "commitBatch|commitState|commitBatchWithProof",
                            method)
            res["verdict"] = "coverage_debt"
            res["coverage"] = coverage
            return res
        ok_status = rec["receipt_status"] == 1
        if isinstance(dec_dec, dict) and dec_dec.get("$", "").endswith("_Rev"):
            model_outcome = "Rev"
            code = dec_dec["code"]
            checks.add("outcome", "ok" if ok_status else f"rev:{code}",
                       f"Rev{{{code}}} {REASONS.get(code, '?')}",
                       "agree" if not ok_status else "extraction_defect",
                       f"model reverted reason {code} "
                       f"({REASONS.get(code, '?')}); receipt.status="
                       f"{rec['receipt_status']}")
        elif isinstance(dec_dec, dict) and dec_dec.get("$", "").endswith("_Ok"):
            model_outcome = "Ok"
            checks.add("outcome", ok_status, True,
                       "agree" if ok_status else "real_defect",
                       "model Ok; receipt.status=" + str(rec["receipt_status"]))
        else:
            model_outcome = "?"
            err = repr(dec_dec)[:200]
            if ("largest immediate" in err
                    and len(blobs_for_model) >= 2):
                # d_blob_hash's nested Cantor pairing b_pair(a,b) =
                # (a+b)(a+b+1)/2 + b grows ~a^(2^k) in k blobs; for >= 2
                # blob atoms it overflows Bend's 2^48 Nat immediate.
                checks.disagree(
                    "outcome", "extraction_defect", "Dec ctor", err,
                    rule="benc_pair_overflow",
                    evidence={"blobs": len(blobs_for_model),
                              "atoms": blobs_for_model,
                              "formula": "b_enc nests b_pair: value grows "
                                         "~a^(2^k); commit-local atoms "
                                         "2..k+1 overflow Nat 2^48 for "
                                         "k>=5 blobs (k=4 peaks ~7.2e8)"})
            else:
                checks.disagree("outcome", "oracle_mismatch", "Dec ctor",
                                err)
        res["model_outcome"] = model_outcome
        res["model_decision"] = dec_dec
        if model_outcome == "Ok" and ok_status and isinstance(st2, dict):
            self._post_checks(checks, st2, c, inp, pre, post, rec, idx,
                              ver_new, n, lbn, prev_a, post_a,
                              successor_parent)
        res["coverage"] = coverage
        bad = [x for x in checks.items if x["verdict"] != "agree"]
        res["verdict"] = ("agree" if not bad else
                          bad[0]["verdict"])
        res["n_checks"] = len(checks.items)
        return res

    def _st_args(self, st: dict, tags: bool = False):
        """The flat arg prefix decide_* wants (state fields in order)."""
        args = [st["t"], st["lfi"], st["inch"], st["bc"], st["rri"],
                st["paused"], st["W"], st["D"], st["qlen"], st["qpend"],
                st["enq"], st["active"], st["chs"], st["win"], st["s_bvh"]]
        if tags:
            args.append(st["s_tag"])
        return args

    def _field_cross(self, checks: Checks, dec: dict, pre: dict,
                     parent_idx: int):
        """Cross-check decoded parent-header fields vs pre-state reads."""
        ent = None
        for e in pre["window"]["entries"]:
            if e["index"] == parent_idx:
                ent = e
                break
        if ent is None:
            return
        mapping = [
            ("blobVersionedHash", "bvh"), ("prevStateHash", "prev"),
            ("postStateHash", "post"),
        ]
        for field, key in mapping:
            if field in dec and ent.get(key) is not None:
                got = b2h(dec[field])
                exp = canon_b32(ent[key])
                checks.add(f"dec.{field}_vs_entry", exp, got,
                           "agree" if got == exp else "oracle_mismatch",
                           "decoded parent header field vs stored entry value")
        if ent.get("tot") is not None and "totalL1MessagePopped" in dec:
            got = be_int(dec["totalL1MessagePopped"])
            checks.add("dec.tot_vs_entry", ent["tot"], got,
                       "agree" if got == ent["tot"] else "oracle_mismatch")
        if ent.get("lbn") is not None and "lastBlockNumber" in dec:
            got = be_int(dec["lastBlockNumber"])
            checks.add("dec.lbn_vs_entry", ent["lbn"], got,
                       "agree" if got == ent["lbn"] else "oracle_mismatch")

    def _post_checks(self, checks: Checks, st2: dict, c: dict, inp: dict,
                     pre: dict, post: dict, rec: dict, idx: int,
                     ver_new: int, n: int, lbn: int, prev_a: int, post_a: int,
                     successor_parent: bytes | None):
        atoms = self.atoms
        new = st2["win"][-1] if st2.get("win") else None
        lci2 = self.machine("lci_of", st2)
        checks.add("post.lci", idx, lci2,
                   "agree" if lci2 == idx else "extraction_defect")
        checks.add("post.lastCommittedBatchIndex", idx,
                   post["lastCommittedBatchIndex"],
                   "agree" if post["lastCommittedBatchIndex"] == idx
                   else "real_defect")
        if not isinstance(new, dict):
            checks.disagree("post.newest_entry", "oracle_mismatch",
                            "HEntry", repr(new)[:120])
            return
        # concrete post-state vs new entry (atoms)
        csr_stored = canon_b32(post["committedStateRoots"])
        checks.add("post.csr", atoms.atom(csr_stored), new["csr"],
                   "agree" if new["csr"] == atoms.atom(csr_stored)
                   else "extraction_defect",
                   "entry.csr vs committedStateRoots[idx]")
        checks.add("post.csr_vs_input_post", post_a, new["csr"],
                   "agree" if new["csr"] == post_a else "real_defect",
                   "stored csr should equal calldata postStateRoot")
        # entry.bvh is a symbolic atom for v2 (d_blob_hash abstracts keccak),
        # concrete for legacy. Compare against the model's own d_blob_hash
        # output — the concrete stored value is checked in bvh_stored_vs_*
        model_bvh = self.machine("d_blob_hash", ver_new,
                                 self.atoms.model_blob_atoms(
                                     ver_new,
                                     [canon_b32(h) for h in
                                      c.get("blob_versioned_hashes", [])]))
        checks.add("post.bvh", model_bvh, new["bvh"],
                   "agree" if new["bvh"] == model_bvh else "extraction_defect",
                   "entry.bvh vs d_blob_hash(ver,blobs) output")
        checks.add("post.hb_eq_bvh", new["bvh"], new["hb"],
                   "agree" if new["hb"] == new["bvh"] else "extraction_defect",
                   "entry.hb written from same bvh")
        store = post.get("batchDataStore") or {}
        if store:
            checks.add("post.bdo", store["originTimestamp"], new["bdo"],
                       "agree" if new["bdo"] == store["originTimestamp"]
                       else "extraction_defect")
            checks.add("post.bdf", store["finalizeTimestamp"], new["bdf"],
                       "agree" if new["bdf"] == store["finalizeTimestamp"]
                       else "extraction_defect",
                       "model bdf=t+F+prt")
            checks.add("post.bdn", store["blockNumber"], new["bdn"],
                       "agree" if new["bdn"] == store["blockNumber"]
                       else "extraction_defect")
            checks.add("post.bdn_vs_input_lbn", lbn, store["blockNumber"],
                       "agree" if lbn == store["blockNumber"]
                       else "real_defect")
            checks.add("post.bds", atoms.atom(canon_addr(store["submitter"])),
                       new["bds"],
                       "agree" if new["bds"] ==
                       atoms.atom(canon_addr(store["submitter"]))
                       else "extraction_defect")
        checks.add("post.ver", ver_new, new["ver"],
                   "agree" if new["ver"] == ver_new else "extraction_defect")
        checks.add("post.lbn", lbn, new["lbn"],
                   "agree" if new["lbn"] == lbn else "extraction_defect")
        checks.add("post.n", n, new["n"],
                   "agree" if new["n"] == n else "extraction_defect")
        checks.add("post.prev", prev_a, new["prev"],
                   "agree" if new["prev"] == prev_a else "extraction_defect")
        checks.add("post.post", post_a, new["post"],
                   "agree" if new["post"] == post_a else "extraction_defect")
        checks.add("post.tag", 2 if ver_new == 2 else 1, new["tag"],
                   "agree" if new["tag"] == (2 if ver_new == 2 else 1)
                   else "extraction_defect")
        # prt: bdf - t - F must equal model prt (chain gives finalizeTimestamp)
        if store:
            prt_real = store["finalizeTimestamp"] - rec["pre"]["t"] - \
                rec["pre"]["scalars"]["F"]
            sc = rec["pre"]["scalars"]
            cstart = 0
            for ch in rec["pre"]["challenges"]:
                if ch["index"] == sc["bc"]:
                    cstart = ch["startTime"]
            prt_model = self.oracle_prt(sc["inch"], sc["W"], cstart,
                                        rec["pre"]["t"])
            checks.add("post.prt", prt_model, prt_real,
                       "agree" if prt_real == prt_model else "real_defect",
                       f"stored bdf-t-F={prt_real} vs inch/W/cstart "
                       f"formula {prt_model}")
        # successor's presented parent header vs the new entry (chain link)
        if successor_parent:
            dec_s = self.m_dec_go(successor_parent)
            if dec_s is not None:
                checks.add("succ.version", ver_new, be_int(dec_s["version"]),
                           "agree" if be_int(dec_s["version"]) == ver_new
                           else "real_defect")
                for f, k in (("prevStateHash", "prev"),
                             ("postStateHash", "post")):
                    if f in dec_s:
                        got = atoms.atom(b2h(dec_s[f]))
                        checks.add(f"succ.{f}", new[k], got,
                                   "agree" if got == new[k]
                                   else "real_defect",
                                   "successor's parent header field vs "
                                   "model new entry")
                if "totalL1MessagePopped" in dec_s:
                    got = be_int(dec_s["totalL1MessagePopped"])
                    checks.add("succ.tot", new["tot"], got,
                               "agree" if got == new["tot"]
                               else "real_defect")
                if "lastBlockNumber" in dec_s:
                    got = be_int(dec_s["lastBlockNumber"])
                    checks.add("succ.lbn", new["lbn"], got,
                               "agree" if got == new["lbn"]
                               else "real_defect")
                kh = self.ms.keccak(successor_parent)
                cb_next = post.get("committedBatches")
                checks.add("succ.batch_hash", canon_b32(cb_next)
                           if cb_next else None, canon_b32(kh),
                           "agree" if cb_next is not None and
                           canon_b32(cb_next) == canon_b32(kh)
                           else ("real_defect" if cb_next else "agree"),
                           "keccak(successor parent header) vs "
                           "committedBatches[idx]")
        else:
            checks.add("succ.parent_header", None, None, "coverage_debt",
                       "no successor commit supplied: committedBatches[idx] "
                       "not verifiable by chain linkage")
        # invariant spot-check on the post state
        tags = self.machine("tags_ok", st2)
        checks.add("inv.tags_ok", True, tags,
                   "agree" if tags is True else "extraction_defect")


def _load_records(records_dir: Path, idx: int) -> dict | None:
    p = records_dir / "commits" / f"{idx}.json"
    if p.exists():
        return json.loads(p.read_text())
    return None


def run(manifest_path: Path, records_dir: Path | None, store: PayloadStore,
        out_path: Path, header_mjs: str, machine_mjs: str,
        limit: int | None = None) -> dict:
    manifest = json.loads(manifest_path.read_text())
    atoms = AtomMap()
    report = {
        "unit": "S6", "spec": "M2_SPEC §3 row S6, whitepaper §8.7",
        "chain": manifest["chain"], "rollup_proxy": manifest["rollup_proxy"],
        "window": manifest["window"], "morph_commit":
        "3e44e795586af3e11285b603ab642c67823add51",
        "commits": [], "disagreements": [], "coverage": [],
        "summary": {},
    }
    commits = sorted(manifest["commits"], key=lambda c: c["batch_index"])
    if limit:
        commits = commits[:limit]
    with ModelSession(header_mjs, machine_mjs) as ms:
        eng = Replay(ms, atoms)
        succ_parent = None
        for i, c in enumerate(commits):
            calldata = store.resolve(c["calldata_sha256"])
            rec = _load_records(records_dir, c["batch_index"]) if records_dir else None
            if rec is None:
                res = {"batch_index": c["batch_index"], "tx": c["tx"],
                       "verdict": "oracle_mismatch",
                       "checks": [{"check": "pre_state_record",
                                   "verdict": "oracle_mismatch",
                                   "detail": "no reconstruction record"}]}
                report["commits"].append(res)
                continue
            # the next commit's parent header = this commit's new header —
            # ONLY when the manifest's next entry is the actual successor
            # batch (non-contiguous corpora must use the record's stored
            # successor parent instead of the next manifest entry's, which
            # is that entry's own parent)
            nxt = commits[i + 1] if i + 1 < len(commits) else None
            succ_parent = None
            if (nxt is not None
                    and nxt.get("batch_index") == c["batch_index"] + 1):
                try:
                    succ_parent = decode_commit_input(
                        nxt.get("method") or "commitBatch",
                        store.resolve(nxt["calldata_sha256"]))["parentBatchHeader"]
                except Exception:
                    succ_parent = None
            if succ_parent is None and rec.get("successor_parent_header"):
                succ_parent = h2b(rec["successor_parent_header"])
            res = eng.replay_commit(c, rec, calldata, succ_parent)
            report["commits"].append(res)
            report["coverage"].extend(res.pop("coverage", []))
    # aggregate
    counts = {k: 0 for k in Checks.CATEGORIES}
    counts["unexplained"] = 0
    dis = []
    for r in report["commits"]:
        for chk in r.get("checks", []):
            v = chk["verdict"]
            counts[v] = counts.get(v, 0) + 1
            if chk.get("unexplained"):
                counts["unexplained"] += 1
            if v != "agree":
                d = {"batch_index": r["batch_index"],
                     "check": chk["check"], "verdict": v,
                     "expected": chk.get("expected"),
                     "got": chk.get("got"),
                     "detail": chk.get("detail", "")}
                if chk.get("rule"):
                    d["rule"] = chk["rule"]
                    d["evidence"] = chk.get("evidence")
                if chk.get("unexplained"):
                    d["unexplained"] = True
                dis.append(d)
    report["disagreements"] = dis
    report["summary"] = {
        "n_commits": len(report["commits"]),
        "n_checks": sum(r.get("n_checks", len(r.get("checks", [])))
                        for r in report["commits"]),
        "per_verdict": counts,
        "commit_verdicts": {str(r["batch_index"]): r["verdict"]
                            for r in report["commits"]},
        "atoms": atoms.table(),
        "coverage_items": report["coverage"],
        "n_unexplained": counts["unexplained"],
        "threshold": {"min_commits": 200, "max_unexplained": 0,
                      "met": counts["unexplained"] == 0
                      and len(report["commits"]) >= 200},
        "notes": [
            "atoms: 0=zero value, 1=ZERO_VERSIONED_HASH, >=10000 first-seen",
            "hb field of entries = bvh atom (model convention: "
            "exec_commitBatch writes hb:=bvh)",
            "fsr/chals reconstructed empty: never read on the commitBatch "
            "edge; recorded as reconstruction notes not coverage debt",
            "enq prefix below qpend elided: d_enq_first reads only "
            "enq[qpend]",
            "finalizeBatch(i+1) deletes batchDataStore/committedStateRoots/"
            "batchBlobVersionedHashes[i]: window store fields are read at "
            "each commit's own pre-block, not at a shared snapshot",
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n")
    return report


def _find_artifact(name: str) -> str:
    """Locate the newest compiled artifact for a model name under build/."""
    best = None
    for p in (REPO / "build" / "eval").glob(f"*/{name}.mjs"):
        if best is None or p.stat().st_mtime > best.stat().st_mtime:
            best = p
    if best is None:
        raise FileNotFoundError(
            f"no compiled {name}.mjs under build/eval — run the generators first")
    return str(best)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon.hist.replay")
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--records", type=Path, default=None,
                    help="dir containing commits/<idx>.json reconstruction "
                         "records (fixtures dir for the S6 fixture)")
    ap.add_argument("--payload-dir", type=Path, default=None,
                    help="dir of <sha256>.json payload files (fixtures)")
    ap.add_argument("--cache-dir", type=Path,
                    default=Path(os.environ.get(
                        "HOLON_CACHE", "~/.holon/cache/m2")).expanduser())
    ap.add_argument("--out", type=Path, default=REPO / "replay/M2/report.json")
    ap.add_argument("--header-mjs", default=None)
    ap.add_argument("--machine-mjs", default=None)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    header_mjs = a.header_mjs or _find_artifact("morph_header")
    machine_mjs = a.machine_mjs or _find_artifact("morph_rollup")
    rep = run(a.manifest, a.records, PayloadStore(a.cache_dir, a.payload_dir),
              a.out, header_mjs, machine_mjs, a.limit)
    s = rep["summary"]
    print(f"S6 replay: {s['n_commits']} commits, {s['n_checks']} checks, "
          f"verdicts={s['per_verdict']}")
    for d in rep["disagreements"][:20]:
        print(f"  ! batch {d['batch_index']} {d['check']}: {d['verdict']}"
              f" — {d['detail'][:100]}")
    print(f"wrote {a.out}")
    return 0 if all(v == 0 for k, v in s["per_verdict"].items()
                    if k not in ("agree", "coverage_debt")) else 1


if __name__ == "__main__":
    sys.exit(main())
