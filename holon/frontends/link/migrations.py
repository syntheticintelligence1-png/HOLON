"""Emit spec/M2/extracted/migrations.json: L1 proxy deployment history.

For each in-scope proxy (Rollup, L1MessageQueue):

* deploy record — creation tx, decoded constructor args (initial impl, admin,
  init data);
* upgrades — every ``Upgraded`` event: block, tx hash, log index, new impl,
  the peeled admin call chain, and the decoded reinitializer call (function,
  signature, reinitializer version, named args) when bundled;
* admin history — every ``AdminChanged`` event;
* impl details — runtime code size/hash, sourcify verification + compiler,
  source match against the pinned repo commit and known tags;
* storage layouts per implementation and diffs between successive impls;
* the M1 ``migrations`` facts mapped onto on-chain anchors.
"""

import hashlib
import json

from . import calls
from .chain import ADMIN_CHANGED_TOPIC, ADMIN_SLOT, IMPL_SLOT, UPGRADED_TOPIC
from .layout import diff_layouts, normalize_layout

PROXY_ADMIN = "0x31110622d6ca24c9ff307d6ae1715f16e47f16a0"
ADMIN_OWNER = "0x542675e90e269f20ecbb9e0095d4751ac155b530"
EMPTY_CONTRACT = "0x98df320641c2e65ab4bbef1e6f6c66d9b50ede5f"
DEPLOYER = "0x2818a3af785975a32611155a6ee36c21cec068ca"


def _b(hexword):
    return int(hexword, 16)


def _decode_ctor_args(input_hex, expected_impl):
    """Locate (address impl, address admin, bytes data) appended to initcode.

    Scans 32-byte-aligned tails from the end of the creation input; the first
    tail that ABI-decodes to impl==expected_impl and a plausible admin wins.
    """
    data = input_hex[2:] if input_hex.startswith("0x") else input_hex
    b = bytes.fromhex(data)
    for start in range(len(b) - 96, 32, -32):
        tail = b[start:]
        impl = tail[12:32].hex()
        admin = tail[44:64].hex()
        off = int.from_bytes(tail[64:96], "big")
        if impl == expected_impl[2:] and off == 96:
            blen = int.from_bytes(tail[96:128], "big") if len(tail) >= 128 else 0
            blob = tail[128:128 + blen]
            return {"initial_impl": "0x" + impl, "initial_admin": "0x" + admin,
                    "init_data": "0x" + blob.hex() if blen else "",
                    "init_data_empty": blen == 0}
    return {"initial_impl": expected_impl, "init_data_empty": None,
            "note": "constructor args not located; impl taken from Upgraded event"}


def _impl_details(impl, record, sourcify_dir, layouts_dir):
    code = record["codes"].get(impl, "")
    det = {"address": impl,
           "code_size": (len(code) - 2) // 2 if code else None,
           "runtime_code_sha256": ("0x" + hashlib.sha256(bytes.fromhex(code[2:])).hexdigest())
           if code else None}
    d = sourcify_dir / impl
    if (d / "_meta.json").exists():
        meta = json.loads((d / "_meta.json").read_text())
        det["verified"] = True
        det["sourcify"] = {k: meta.get(k) for k in
                           ("name", "compilerVersion", "match", "runtimeMatch", "n_sources")}
        src_hashes = {}
        for rel in meta.get("files", []):
            p = d / rel
            if p.exists():
                src_hashes[rel] = "0x" + hashlib.sha256(p.read_bytes()).hexdigest()
        det["source_sha256"] = src_hashes
    else:
        det["verified"] = False
    lf = layouts_dir / f"{impl}.json"
    if lf.exists():
        det["storage_layout"] = json.loads(lf.read_text())
    return det


def build_migrations(record, sourcify_dir, layouts_dir, proxies):
    """`record` is the chain capture:
    {"logs": {addr|topic: [logs]}, "txs": {hash: tx}, "codes": {addr: hex},
     "slots": {addr|slot|label: value}, "impl_meta": {addr: {repo_pin_match, repo_tag}}}.
    """
    out = {"schema": "holon.migrations/v1",
           "chain": {"name": "ethereum", "chain_id": 1},
           "proxies": [], "storage_diffs": [], "m1_facts": {}}
    coverage = []

    for px in proxies:
        addr = px["address"].lower()
        plogs = sorted(record["logs"].get(f"{addr}|{UPGRADED_TOPIC}", []),
                       key=lambda l: (_b(l["blockNumber"]), _b(l["logIndex"])))
        alogs = sorted(record["logs"].get(f"{addr}|{ADMIN_CHANGED_TOPIC}", []),
                       key=lambda l: (_b(l["blockNumber"]), _b(l["logIndex"])))
        prec = {"name": px["name"], "contract": px["contract"], "address": addr,
                "kind": "TransparentUpgradeableProxy",
                "implementation_slot": IMPL_SLOT, "admin_slot": ADMIN_SLOT,
                "admin_history": [], "upgrades": []}

        # deploy = tx of the first Upgraded event
        if plogs:
            first = plogs[0]
            tx = record["txs"].get(first["transactionHash"], {})
            prec["deploy"] = {
                "block": _b(first["blockNumber"]), "tx": first["transactionHash"],
                "deployer": tx.get("from"),
                **_decode_ctor_args(tx.get("input", ""), "0x" + first["topics"][1][-40:]),
            }

        for l in alogs:
            d = l["data"][2:]
            prec["admin_history"].append({
                "block": _b(l["blockNumber"]), "tx": l["transactionHash"],
                "log_index": _b(l["logIndex"]),
                "previous_admin": "0x" + d[24:64], "new_admin": "0x" + d[88:128]})

        impl_seq = []
        for i, l in enumerate(plogs):
            impl = "0x" + l["topics"][1][-40:]
            tx = record["txs"].get(l["transactionHash"], {})
            steps = calls.decode_upgrade_input(tx.get("to"), tx.get("input", ""),
                                               tx.get("from"))
            init_data = None
            via = []
            for s in steps:
                if s["kind"] == "tx_head":
                    via.append({"kind": "tx_from", "address": s.get("from")})
                elif s["kind"] == "safe_exec":
                    via.append({"kind": "gnosis_safe", "address": tx.get("to"),
                                "inner_target": s["to"]})
                elif s["kind"] == "opaque_wrapper":
                    via.append({"kind": "admin_wrapper"})
                elif s["kind"] == "proxyadmin_upgrade":
                    via.append({"kind": "proxy_admin", "address": PROXY_ADMIN,
                                "function": s["function"]})
                    init_data = s.get("init_data")
                elif s["kind"] == "proxy_upgrade":
                    via.append({"kind": "proxy", "function": s["function"]})
                    init_data = s.get("init_data") or init_data
            ctor = i == 0 and impl == EMPTY_CONTRACT
            up = {"seq": i, "impl": impl, "block": _b(l["blockNumber"]),
                  "tx": l["transactionHash"], "log_index": _b(l["logIndex"]),
                  "via": via}
            if i == 0:
                up["via"] = [{"kind": "constructor"}]
            if init_data:
                up["init_data_raw"] = init_data
            prec["upgrades"].append(up)
            impl_seq.append(impl)

        # impl details + reinit decode (needs abi)
        details = {}
        for up in prec["upgrades"]:
            impl = up["impl"]
            if impl not in details:
                details[impl] = _impl_details(impl, record, sourcify_dir, layouts_dir)
            abi = []
            af = sourcify_dir / impl / "abi.json"
            if af.exists():
                abi = json.loads(af.read_text())
            if up.get("init_data_raw"):
                reinit = calls.decode_initializer(up.pop("init_data_raw"), abi)
                if reinit:
                    up["reinit"] = reinit
            meta = record.get("impl_meta", {}).get(impl, {})
            if meta:
                details[impl]["repo_pin_match"] = meta.get("repo_pin_match")
                details[impl]["repo_tag"] = meta.get("repo_tag")

        prec["current_impl_slot"] = record["slots"].get(f"{addr}|{IMPL_SLOT}")
        prec["current_admin_slot"] = record["slots"].get(f"{addr}|{ADMIN_SLOT}")
        prec["implementations"] = [details[i] for i in impl_seq]
        out["proxies"].append(prec)

        # storage diffs between successive impls
        src_sets = {}
        for i in impl_seq:
            det = details[i]
            src_sets[i] = frozenset(det.get("source_sha256", {}).values()) or None
        for a, b in zip(impl_seq, impl_seq[1:]):
            da, db = details[a], details[b]
            if a == b:
                continue
            entry = {"proxy": px["name"], "from_impl": a, "to_impl": b}
            if src_sets[a] is not None and src_sets[a] == src_sets[b]:
                entry["status"] = "identical_source"
                entry.update({"added": [], "removed": [], "moved": [], "retyped": []})
            elif not (da.get("verified") and db.get("verified")):
                entry["status"] = "unverifiable"
                entry["reason"] = ("unverified implementation source: "
                                   + (a if not da.get("verified") else b))
                coverage.append({"element": f"chain:{a}->{b}",
                                 "kind": "unverified_source",
                                 "reason": entry["reason"]})
            elif "storage_layout" in da and "storage_layout" in db:
                entry["status"] = "diffed"
                entry.update(diff_layouts(da["storage_layout"], db["storage_layout"]))
            else:
                entry["status"] = "no_layout"
                coverage.append({"element": f"chain:{a}->{b}", "kind": "missing_layout",
                                 "reason": "solc storage layout unavailable"})
            out["storage_diffs"].append(entry)

    # M1 facts anchors: the upgrade carrying initialize2 is eta2's anchor.
    for prec in out["proxies"]:
        if prec["name"] != "Rollup":
            continue
        for up in prec["upgrades"]:
            r = up.get("reinit") or {}
            if r.get("function") == "initialize2":
                out["m1_facts"]["eta2"] = {
                    "upgrade_seq": up["seq"], "block": up["block"], "tx": up["tx"],
                    "impl": up["impl"], "reinitializer_version": r["reinitializer_version"],
                    "function": r["function"],
                    "writes": "committedStateRoots[LCI] = _prevStateRoot if currently zero",
                    "m1_src": "contracts/contracts/l1/rollup/Rollup.sol:188-195"}
            if r.get("function") in ("initialize3", "initialize4"):
                out["m1_facts"].setdefault("later_reinitializers", []).append(
                    {"upgrade_seq": up["seq"], "block": up["block"], "tx": up["tx"],
                     "function": r["function"], "version": r["reinitializer_version"],
                     "args": r.get("args")})
        out["m1_facts"]["legacy"] = {
            "meaning": "storage as written before reinitializer(2): "
                       "committedStateRoots did not exist (all zero)",
            "until_upgrade_seq": (out["m1_facts"].get("eta2") or {}).get("upgrade_seq")}
    out["coverage"] = coverage
    return out
