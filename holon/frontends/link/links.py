"""Emit spec/M2/extracted/links.json: cross-language linking facts.

Sections:

* constants — the shared literals registry (consts.py);
* wire_layout — per-field byte offsets of the batch header, mechanically
  recovered from the Solidity mstore sites and the Go copy/PutUint64 sites;
* abi_bindings — Go binding embedded ABI vs the deployed implementation ABI
  for the in-scope contracts (plus an inventory of all bindings);
* event_schemas — every event in the deployed ABIs, with topic0 and the Go
  binding's filter/parse support.
"""

import hashlib
import json
import re

from . import abi as A
from . import consts
from . import gobind

# Canonical batch-header wire layout shared by both encoders (the linking
# target; each field has its own mechanical extractors below).
WIRE_FIELDS = [
    {"name": "version", "offset": 0, "width": 1},
    {"name": "batchIndex", "offset": 1, "width": 8},
    {"name": "l1MessagePopped", "offset": 9, "width": 8},
    {"name": "totalL1MessagePopped", "offset": 17, "width": 8},
    {"name": "dataHash", "offset": 25, "width": 32},
    {"name": "blobVersionedHash", "offset": 57, "width": 32},
    {"name": "prevStateRoot", "offset": 89, "width": 32},
    {"name": "postStateRoot", "offset": 121, "width": 32},
    {"name": "withdrawalRoot", "offset": 153, "width": 32},
    {"name": "sequencerSetVerifyHash", "offset": 185, "width": 32},
    {"name": "parentBatchHash", "offset": 217, "width": 32},
    {"name": "lastBlockNumber", "offset": 249, "width": 8},
]

# Solidity store sites: BatchHeaderCodecV0.sol mstore/mstore8 lines; the field
# name is derived from the store function's argument. BatchHeaderCodecV1.sol
# contributes lastBlockNumber at 249.
_SOL_STORES = {
    "version": ("contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol",
                r"mstore8\(batchPtr,\s*_version\)"),
    "batchIndex": ("contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol",
                   r"mstore\(add\(batchPtr,\s*(\d+)\),\s*shl\(192,\s*_batchIndex\)\)"),
    "l1MessagePopped": ("contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol",
                        r"mstore\(add\(batchPtr,\s*(\d+)\),\s*shl\(192,\s*_l1MessagePopped\)\)"),
    "totalL1MessagePopped": ("contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol",
                             r"mstore\(add\(batchPtr,\s*(\d+)\),\s*shl\(192,\s*_totalL1MessagePopped\)\)"),
    "dataHash": ("contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol",
                 r"mstore\(add\(batchPtr,\s*(\d+)\),\s*_dataHash\)"),
    "blobVersionedHash": ("contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol",
                          r"mstore\(add\(batchPtr,\s*(\d+)\),\s*_blobVersionedHash\)"),
    "prevStateRoot": ("contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol",
                      r"mstore\(add\(batchPtr,\s*(\d+)\),\s*_prevStateHash\)"),
    "postStateRoot": ("contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol",
                      r"mstore\(add\(batchPtr,\s*(\d+)\),\s*_postStateHash\)"),
    "withdrawalRoot": ("contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol",
                       r"mstore\(add\(batchPtr,\s*(\d+)\),\s*_withdrawRootHash\)"),
    "sequencerSetVerifyHash": ("contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol",
                               r"mstore\(add\(batchPtr,\s*(\d+)\),\s*_sequencerSetVerifyHash\)"),
    "parentBatchHash": ("contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol",
                        r"mstore\(add\(batchPtr,\s*(\d+)\),\s*_parentBatchHash\)"),
    "lastBlockNumber": ("contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol",
                        r"mstore\(add\(batchPtr,\s*(\d+)\),\s*shl\(192,\s*_lastBlockNumber\)\)"),
}

# Go write sites: batch_header.go encoders (BatchHeaderV0/V1 Bytes()).
_GO_WRITES = {
    "version": (r"batchBytes\[0\]\s*=\s*BatchHeaderVersion\d"),
    "batchIndex": (r"binary\.BigEndian\.PutUint64\(batchBytes\[1:\],\s*b\.BatchIndex\)"),
    "l1MessagePopped": (r"binary\.BigEndian\.PutUint64\(batchBytes\[9:\],\s*b\.L1MessagePopped\)"),
    "totalL1MessagePopped": (r"binary\.BigEndian\.PutUint64\(batchBytes\[17:\],\s*b\.TotalL1MessagePopped\)"),
    "dataHash": (r"copy\(batchBytes\[25:\],\s*b\.DataHash\[:\]\)"),
    "blobVersionedHash": (r"copy\(batchBytes\[57:\],\s*b\.BlobVersionedHash\[:\]\)"),
    "prevStateRoot": (r"copy\(batchBytes\[89:\],\s*b\.PrevStateRoot\[:\]\)"),
    "postStateRoot": (r"copy\(batchBytes\[121:\],\s*b\.PostStateRoot\[:\]\)"),
    "withdrawalRoot": (r"copy\(batchBytes\[153:\],\s*b\.WithdrawalRoot\[:\]\)"),
    "sequencerSetVerifyHash": (r"copy\(batchBytes\[185:\],\s*b\.SequencerSetVerifyHash\[:\]\)"),
    "parentBatchHash": (r"copy\(batchBytes\[217:\],\s*b\.ParentBatchHash\[:\]\)"),
    "lastBlockNumber": (r"binary\.BigEndian\.PutUint64\(batchBytes\[249:\],\s*b\.LastBlockNumber\)"),
}
_GO_FILE = "common/batch/batch_header.go"


def _first_line(text, rx):
    r = re.compile(rx)
    for i, line in enumerate(text.splitlines(), 1):
        m = r.search(line)
        if m:
            return i, line.strip(), (m.group(1) if m.groups() else None)
    return None, None, None


def extract_wire_layout(repo):
    """Recover each header field's offset on both sides and compare."""
    cache = {}

    def lines(rel):
        if rel not in cache:
            cache[rel] = (repo / rel).read_text(encoding="utf-8")
        return cache[rel]

    fields = []
    for f in WIRE_FIELDS:
        rec = {"name": f["name"], "offset": f["offset"], "width": f["width"]}
        sfile, spat = _SOL_STORES[f["name"]]
        lno, code, lit = _first_line(lines(sfile), spat)
        # mstore8(batchPtr, _version) writes at offset 0 (no add() term).
        sol_off = int(lit) if lit is not None else (0 if lno else None)
        rec["solidity"] = ({"file": sfile, "line": lno, "code": code, "offset": sol_off}
                           if lno else None)
        lno2, code2, _ = _first_line(lines(_GO_FILE), _GO_WRITES[f["name"]])
        m = re.search(r"batchBytes\[(\d+):\]|batchBytes\[(\d+)\]", code2 or "")
        go_off = int(m.group(1) or m.group(2)) if m else None
        rec["go"] = ({"file": _GO_FILE, "line": lno2, "code": code2, "offset": go_off}
                     if lno2 else None)
        rec["linked"] = bool(sol_off == f["offset"] and go_off == f["offset"]
                             and rec["solidity"] and rec["go"])
        fields.append(rec)
    return fields


def _by_kind(abi_list, kind):
    return [e for e in abi_list if e.get("type") == kind]


def build_links(repo, sourcify_dir, proxies):
    """Full links.json payload. `proxies` = chain.PROXIES entries that also
    carry `impl_abi` (deployed ABI) via `current_impl` when the caller supplies
    them; see migrations.build_migrations for the chain side."""
    out = {
        "schema": "holon.links/v1",
        "target": {"repo": "morph-l2/morph"},
        "constants": consts.extract_constants(repo),
        "wire_layout": extract_wire_layout(repo),
        "abi_bindings": [],
        "event_schemas": [],
        "bindings_inventory": [],
    }
    bindings_dir = repo / "bindings" / "bindings"
    for gf in sorted(bindings_dir.glob("*.go")):
        p = gobind.parse_go_binding(gf)
        out["bindings_inventory"].append({
            "file": f"bindings/bindings/{gf.name}",
            "contract": p["contract"],
            "abi_entries": len(p["abi"]) if p["abi"] else 0,
            "bin_present": p["bin_present"],
        })

    for px in proxies:
        bind_rel = px["binding"]
        parsed = gobind.parse_go_binding(repo / bind_rel)
        go_abi = parsed["abi"] or []
        deployed = px.get("impl_abi") or []
        entry = {
            "contract": px["contract"],
            "go_file": bind_rel,
            "binding_abi_sha256": "0x" + hashlib.sha256(
                json.dumps(go_abi, sort_keys=True).encode()).hexdigest(),
            "binding_abi_entries": len(go_abi),
        }
        if deployed:
            entry["reference"] = {"kind": "deployed_impl",
                                  "address": px.get("current_impl"),
                                  "abi_source": "sourcify",
                                  "abi_sha256": "0x" + hashlib.sha256(
                                      json.dumps(deployed, sort_keys=True).encode()).hexdigest(),
                                  "abi_entries": len(deployed)}
            fd = A.diff_entries(_by_kind(go_abi, "function"), _by_kind(deployed, "function"))
            ed = A.diff_entries(_by_kind(go_abi, "event"), _by_kind(deployed, "event"))
            entry["functions"] = {"shared": fd["shared"], "binding_only": fd["left_only"],
                                  "deployed_only": fd["right_only"],
                                  "indexed_flags_differ": fd["indexed_flags_differ"]}
            entry["events"] = {"shared": ed["shared"], "binding_only": ed["left_only"],
                               "deployed_only": ed["right_only"],
                               "indexed_flags_differ": ed["indexed_flags_differ"]}
            entry["linked"] = not fd["right_only"] and not ed["right_only"]
        else:
            entry["linked"] = "no_reference"
        ev_names = set()
        for s in parsed.get("structs", []):
            c = parsed.get("contract") or ""
            if c and s.startswith(c) and len(s) > len(c):
                ev_names.add(s[len(c):])
        entry["go_event_symbols"] = sorted(ev_names)
        out["abi_bindings"].append(entry)

        for ev in _by_kind(deployed, "event"):
            schema = {
                "contract": px["contract"],
                "name": ev["name"],
                "signature": A.signature(ev),
                "topic0": A.topic0_hex(ev),
                "inputs": A.event_input(ev),
                "go_binding": {
                    "in_embedded_abi": A.signature(ev) in {
                        A.signature(e) for e in _by_kind(go_abi, "event")},
                    "helpers": sorted(
                        set(n for n in parsed.get("functions", [])
                            if n.endswith(ev["name"]) or
                            (n.startswith(("Filter", "Watch", "Parse")) and ev["name"] in n))),
                },
            }
            out["event_schemas"].append(schema)
    out["event_schemas"].sort(key=lambda e: (e["contract"], e["name"], e["signature"]))
    return out
