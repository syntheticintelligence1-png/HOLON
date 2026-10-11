"""Minimal ABI helpers: canonical signatures, selectors/topics, calldata decode.

Only static-size word types plus dynamic `bytes`/`string` decoding are needed
by the link frontend (upgrade calls, initializer calls, Safe.execTransaction).
Anything else decodes as ``None`` and is recorded as debt upstream.
"""

from .keccak import keccak256


def canonical_type(arg):
    t = arg.get("type", "")
    if t.startswith("tuple"):
        comps = ",".join(canonical_type(c) for c in arg.get("components", []))
        suffix = t[5:]
        return f"({comps}){suffix}"
    return t


def signature(entry):
    name = entry.get("name", "")
    args = ",".join(canonical_type(a) for a in entry.get("inputs", []))
    return f"{name}({args})"


def selector(entry):
    return keccak256(signature(entry).encode())[:4]


def selector_hex(entry):
    return "0x" + selector(entry).hex()


def topic0_hex(entry):
    return "0x" + keccak256(signature(entry).encode()).hex()


def is_static(abi_type):
    if abi_type in ("bytes", "string"):
        return False
    if abi_type.endswith("]"):
        base = abi_type.rsplit("[", 1)[0]
        inner = abi_type.rsplit("[", 1)[1][:-1]
        return inner != "" and is_static(base)
    if abi_type == "tuple":
        return True  # caller expands
    return True


def _is_dynamic_type(t):
    return t in ("bytes", "string") or (t.endswith("[]") and not t.endswith("]"))


def decode_words(data, types):
    """ABI-decode `data` (bytes) against a flat list of static/dynamic types.

    Supported: address, bool, uintN/intN, bytesN (static), bytes, string,
    and arrays of the static kinds are returned raw. Returns list of decoded
    values (ints as int, addresses/bytesN as '0x'-hex, bytes as '0x'-hex str).
    Dynamic values not in the supported set yield None.
    """
    words = [data[i * 32:(i + 1) * 32] for i in range(len(data) // 32)]
    out = []
    head_end = 0
    dyn_specs = []
    for i, t in enumerate(types):
        if _is_dynamic_type(t):
            head_end = max(head_end, i + 1)
            dyn_specs.append((i, t))
            out.append(None)
        else:
            if i >= len(words):
                out.append(None)
                continue
            w = words[i]
            if t == "address":
                out.append("0x" + w[12:].hex())
            elif t == "bool":
                out.append(bool(int.from_bytes(w, "big")))
            elif t.startswith("uint") or t.startswith("int"):
                out.append(int.from_bytes(w, "big"))
            elif t.startswith("bytes"):
                out.append("0x" + w[:int(t[5:])].hex())
            else:
                out.append("0x" + w.hex())
            head_end = max(head_end, i + 1)
    for i, t in dyn_specs:
        if i >= len(words):
            continue
        off = int.from_bytes(words[i], "big")
        if off + 32 > len(data):
            continue
        n = int.from_bytes(data[off:off + 32], "big")
        blob = data[off + 32:off + 32 + n]
        out[i] = "0x" + blob.hex()
    return out


def event_input(entry):
    return [
        {"name": a.get("name", ""), "type": canonical_type(a),
         "indexed": bool(a.get("indexed", False))}
        for a in entry.get("inputs", [])
    ]


def function_input(entry):
    return [
        {"name": a.get("name", ""), "type": canonical_type(a)}
        for a in entry.get("inputs", [])
    ]


def diff_entries(left_entries, right_entries):
    """Set-difference on (kind, signature) pairs plus indexed-flag mismatch detection.

    Returns {"shared": [sig...], "left_only": [...], "right_only": [...],
             "sig_same_args_differ": [{signature, left, right}]}.
    left/right are lists of ABI entries (any kinds; compared by signature only).
    """
    def key(e):
        return signature(e)

    lmap = {key(e): e for e in left_entries}
    rmap = {key(e): e for e in right_entries}
    shared = sorted(k for k in lmap if k in rmap)
    left_only = sorted(k for k in lmap if k not in rmap)
    right_only = sorted(k for k in rmap if k not in lmap)
    flags_differ = []
    for k in shared:
        le, re_ = lmap[k], rmap[k]
        li = [(a.get("name", ""), bool(a.get("indexed"))) for a in le.get("inputs", [])]
        ri = [(a.get("name", ""), bool(a.get("indexed"))) for a in re_.get("inputs", [])]
        if [x[1] for x in li] != [x[1] for x in ri]:
            flags_differ.append({"signature": k, "left_indexed": [x[1] for x in li],
                                 "right_indexed": [x[1] for x in ri]})
    return {"shared": shared, "left_only": left_only, "right_only": right_only,
            "indexed_flags_differ": flags_differ}
