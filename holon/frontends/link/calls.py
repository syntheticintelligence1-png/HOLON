"""Decode the call chain of a proxy-upgrade transaction.

Recorded shapes observed on Morph mainnet:

* ``execTransaction(address,uint256,bytes,uint8,...,bytes)`` — a Gnosis Safe
  wrapping an admin call (the proxy admin / its owner contract).
* ``aggregate``-style helpers (e.g. selector ``0x134008d3`` on the ProxyAdmin
  owner) that batch inner calls; decoded by scanning the blob for known
  selectors rather than modelling the helper.
* ProxyAdmin: ``upgrade(address,address)`` and
  ``upgradeAndCall(address,address,bytes)``.
* Transparent proxy: ``upgradeTo(address)`` and
  ``upgradeToAndCall(address,bytes)`` — the trailing bytes are the
  reinitializer call, decoded against the target implementation's ABI.
"""

from .abi import decode_words, signature
from .keccak import keccak256

_SAFE_EXEC = keccak256(b"execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)")[:4].hex()
_SELS = {
    _SAFE_EXEC: "execTransaction",
    keccak256(b"upgrade(address,address)")[:4].hex(): "upgrade",
    keccak256(b"upgradeAndCall(address,address,bytes)")[:4].hex(): "upgradeAndCall",
    keccak256(b"upgradeTo(address)")[:4].hex(): "upgradeTo",
    keccak256(b"upgradeToAndCall(address,bytes)")[:4].hex(): "upgradeToAndCall",
}

_ARG_TYPES = {
    "execTransaction": ["address", "uint256", "bytes", "uint8", "uint256", "uint256",
                        "uint256", "address", "address", "bytes"],
    "upgrade": ["address", "address"],
    "upgradeAndCall": ["address", "address", "bytes"],
    "upgradeTo": ["address"],
    "upgradeToAndCall": ["address", "bytes"],
}


def _sel(data):
    return data[:8] if len(data) >= 8 else None


def _scan_inner(blob):
    """Find embedded known-selector calls inside an opaque bytes blob.

    Scans at 4-byte granularity (selector+args alignments inside aggregates
    are not guaranteed word-aligned), decoding each hit.
    """
    hits = []
    i = 0
    while i + 8 <= len(blob):
        sel = blob[i:i + 8]
        if sel in _SELS:
            name = _SELS[sel]
            args = decode_words(bytes.fromhex(blob[i + 8:]), _ARG_TYPES[name])
            hits.append({"selector": "0x" + sel, "function": name, "args": args})
            i += 8
        else:
            i += 4
    return hits


def _decode_known(data):
    sel = _sel(data)
    if sel not in _SELS:
        return None
    name = _SELS[sel]
    return {"selector": "0x" + sel, "function": name,
            "args": decode_words(bytes.fromhex(data[8:]), _ARG_TYPES[name])}


def decode_upgrade_input(tx_to, input_hex, tx_from=None):
    """Peel a full upgrade tx input into an ordered step list.

    Returns [{"kind","detail"}...] where kinds are:
    tx_head, safe_exec, proxyadmin_upgrade, proxy_upgrade, inner_data and
    unknown_selector / opaque_wrapper markers.
    """
    data = input_hex[2:] if input_hex.startswith("0x") else input_hex
    steps = [{"kind": "tx_head", "to": tx_to, "from": tx_from}]
    pending = [data]
    seen = set()
    while pending:
        blob = pending.pop()
        if blob in seen:
            continue
        seen.add(blob)
        dec = _decode_known(blob)
        if dec is None:
            inner = _scan_inner(blob)
            if inner:
                steps.append({"kind": "opaque_wrapper",
                              "embedded": [f"{x['function']}({','.join(str(a) for a in x['args'])})"
                                           for x in inner]})
                for x in inner:
                    if x["function"] in ("upgrade", "upgradeAndCall"):
                        steps.append({"kind": "proxyadmin_upgrade", "function": x["function"],
                                      "proxy": x["args"][0], "impl": x["args"][1],
                                      "init_data": x["args"][2] if len(x["args"]) > 2 else None})
                    elif x["function"] in ("upgradeTo", "upgradeToAndCall"):
                        steps.append({"kind": "proxy_upgrade", "function": x["function"],
                                      "impl": x["args"][0],
                                      "init_data": x["args"][1] if len(x["args"]) > 1 else None})
            else:
                steps.append({"kind": "unknown_selector", "selector": "0x" + blob[:8]})
            continue
        fn = dec["function"]
        if fn == "execTransaction":
            steps.append({"kind": "safe_exec", "to": dec["args"][0]})
            pending.append((dec["args"][2] or "0x")[2:])
        elif fn in ("upgrade", "upgradeAndCall"):
            steps.append({"kind": "proxyadmin_upgrade", "function": fn,
                          "proxy": dec["args"][0], "impl": dec["args"][1],
                          "init_data": dec["args"][2] if fn == "upgradeAndCall" else None})
            if fn == "upgradeAndCall" and dec["args"][2]:
                pending.append(dec["args"][2][2:])
        elif fn in ("upgradeTo", "upgradeToAndCall"):
            steps.append({"kind": "proxy_upgrade", "function": fn,
                          "impl": dec["args"][0],
                          "init_data": dec["args"][1] if fn == "upgradeToAndCall" else None})
            if fn == "upgradeToAndCall" and dec["args"][1]:
                pending.append(dec["args"][1][2:])
    return steps


def decode_initializer(init_data_hex, impl_abi):
    """Decode a reinitializer payload against the implementation's ABI.

    Matches any function named initialize*; returns {function, signature,
    reinitializer_version, selector, args:{name:value}} or None.
    """
    if not init_data_hex or init_data_hex in ("0x", ""):
        return None
    data = init_data_hex[2:] if init_data_hex.startswith("0x") else init_data_hex
    sel = data[:8]
    for entry in impl_abi or []:
        if entry.get("type") != "function" or not entry.get("name", "").startswith("initialize"):
            continue
        sig = signature(entry)
        if keccak256(sig.encode())[:4].hex() != sel:
            continue
        types = [a["type"] for a in entry.get("inputs", [])]
        vals = decode_words(bytes.fromhex(data[8:]), types)
        name = entry["name"]
        version = 1 if name == "initialize" else int(name.replace("initialize", "") or 1)
        return {"function": name, "signature": sig, "reinitializer_version": version,
                "selector": "0x" + sel,
                "args": {a.get("name", f"arg{i}"): v for i, (a, v) in
                         enumerate(zip(entry.get("inputs", []), vals))}}
    return {"function": None, "selector": "0x" + sel, "raw": "0x" + data[:200],
            "note": "initializer selector not found in implementation ABI"}
