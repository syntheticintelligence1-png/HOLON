"""Recorded-input fetchers for the link frontend.

Every external read goes through a recording wrapper: JSON-RPC calls land in
``chain_record.json`` and Sourcify contract data in ``sourcify/<addr>/`` under
the cache dir. Extraction then reads only the cache, so the committed outputs
are byte-identical given the same recorded inputs (and the manifest pins the
input hashes).
"""

import hashlib
import json
import os
import subprocess
import urllib.request

UPGRADED_TOPIC = "0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b"
ADMIN_CHANGED_TOPIC = "0x7e644d79422f17c01e4894b5f4f588d331ebfa28653d42ae832dc59e38c9798f"
IMPL_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"

PROXIES = [
    {
        "name": "Rollup",
        "contract": "Rollup",
        "address": "0x759894ced0e6af42c26668076ffa84d02e3cef60",
        "binding": "bindings/bindings/rollup.go",
    },
    {
        "name": "L1MessageQueue",
        "contract": "L1MessageQueueWithGasPriceOracle",
        "address": "0x3931ade842f5bb8763164bdd81e5361dce6cc1ef",
        "binding": "bindings/bindings/l1messagequeuewithgaspriceoracle.go",
    },
]

CHAIN_ID = 1


class RpcRecorder:
    """JSON-RPC client that records every response for deterministic replay."""

    def __init__(self, url, record=None, live=True):
        self.url = url
        self.live = live
        self.record = record if record is not None else {"rpc_url": url, "calls": {}}
        self._n = 0

    def _key(self, method, params):
        return method + "|" + json.dumps(params, sort_keys=True)

    def call(self, method, params):
        key = self._key(method, params)
        if key in self.record["calls"]:
            return self.record["calls"][key]["result"]
        if not self.live:
            raise KeyError(f"uncached rpc call {key}")
        body = json.dumps({"jsonrpc": "2.0", "id": self._n, "method": method,
                           "params": params}).encode()
        self._n += 1
        req = urllib.request.Request(self.url, data=body,
                                     headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.load(r)
        if "error" in resp:
            raise RuntimeError(f"rpc {method} failed: {resp['error']}")
        self.record["calls"][key] = {"result": resp["result"]}
        return resp["result"]

    def get_logs(self, address, topic):
        return self.call("eth_getLogs", [{"address": address, "topics": [topic],
                                          "fromBlock": "0x0", "toBlock": "latest"}])

    def get_tx(self, txhash):
        return self.call("eth_getTransactionByHash", [txhash])

    def get_code(self, addr):
        return self.call("eth_getCode", [addr, "latest"])

    def get_storage(self, addr, slot):
        return self.call("eth_getStorageAt", [addr, slot, "latest"])

    def eth_call(self, addr, data):
        return self.call("eth_call", [{"to": addr, "data": data}, "latest"])


def sha256_hex(text):
    return "0x" + hashlib.sha256(text.encode()).hexdigest()


def sha256_hexbytes(hexbytes):
    return "0x" + hashlib.sha256(bytes.fromhex(hexbytes[2:] if hexbytes.startswith("0x") else hexbytes)).hexdigest()


def sourcify_fetch(addr, out_dir):
    """Fetch verified sources + ABI for `addr` on mainnet into out_dir/<addr>/.

    Returns {"verified": bool, "meta": {...}}. Writes sources under their
    declared paths (contracts/..., node_modules/...), plus abi.json and
    _meta.json.
    """
    url = ("https://sourcify.dev/server/v2/contract/%d/%s"
           "?fields=sources,compilation,abi" % (CHAIN_ID, addr))
    req = urllib.request.Request(url, headers={"user-agent": "holon-link/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"verified": False}
        raise
    d = out_dir / addr.lower()
    d.mkdir(parents=True, exist_ok=True)
    sources = data.get("sources") or {}
    for rel, entry in sources.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(entry["content"], encoding="utf-8")
    meta = {
        "address": addr,
        "name": (data.get("compilation") or {}).get("name"),
        "compilerVersion": (data.get("compilation") or {}).get("compilerVersion"),
        "match": data.get("match"),
        "creationMatch": data.get("creationMatch"),
        "runtimeMatch": data.get("runtimeMatch"),
        "compilationTarget": (data.get("compilation") or {}).get("compilationTarget"),
        "n_sources": len(sources),
        "files": sorted(sources.keys()),
    }
    (d / "_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    (d / "abi.json").write_text(json.dumps(data.get("abi") or [], indent=2, sort_keys=True) + "\n")
    return {"verified": True, "meta": meta, "abi": data.get("abi")}


def solc_layout(src_dir, target_rel, contract_name, solc):
    """Run solc --combined-json storage-layout over a sourcify source tree.

    Returns the parsed `storageLayout` object of `<target_rel>:<contract_name>`,
    or {"error": ...} when compilation fails.
    """
    cmd = [solc, "--combined-json", "storage-layout", "--evm-version", "cancun",
           "--base-path", ".", "--include-path", "node_modules",
           target_rel]
    proc = subprocess.run(cmd, cwd=src_dir, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        return {"error": proc.stderr.strip()[:4000]}
    try:
        doc = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "solc emitted non-JSON output: " + proc.stdout[:2000]}
    layouts = doc.get("contracts") or {}
    key = f"{target_rel}:{contract_name}"
    if key in layouts:
        return layouts[key].get("storage-layout") or {"error": "no storage-layout in output"}
    for k, val in layouts.items():
        if k.split(":")[-1] == contract_name:
            return val.get("storage-layout") or {"error": "no storage-layout in output"}
    return {"error": f"compilation target {key} not in outputs: {sorted(layouts)[:20]}"}
