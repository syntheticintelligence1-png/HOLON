"""Parse the generated Go bindings (abigen output) in morph's bindings/ tree.

Each <name>.go file embeds `<Name>MetaData.ABI` — the contract ABI as a Go
string literal (usually concatenated across lines with `+`) — plus event
helper types/functions. We extract the ABI JSON and the event-facing symbol
names so the linking layer can compare them with the deployed Solidity ABI.
"""

import json
import re

_META_RE = re.compile(r"(\w+)MetaData\s*=\s*&bind\.MetaData")


def _go_string_literal(src, start):
    """Parse a Go interpreted string literal (double-quoted, possibly `+`-joined)
    starting at index `start` (position of the opening quote). Returns (value, end)."""
    out = []
    i = start
    while i < len(src):
        if src[i] == '"':
            i += 1
            buf = []
            while i < len(src) and src[i] != '"':
                if src[i] == "\\":
                    buf.append(src[i:i + 2])
                    i += 2
                else:
                    buf.append(src[i])
                    i += 1
            out.append("".join(buf))
            i += 1  # closing quote
            j = i
            while j < len(src) and src[j] in " \t\n":
                j += 1
            if j < len(src) and src[j] == "+":
                i = j + 1
                while i < len(src) and src[i] in " \t\n":
                    i += 1
                continue
            break
        else:
            break
    val = "".join(out)
    # unescape Go escapes (a subset sufficient for embedded JSON)
    val = val.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
    return val, i


def parse_go_binding(path):
    """Returns {contract, file, abi(list), abi_sha256(text), bin_present, symbols}.

    `abi` is the decoded MetaData.ABI JSON list (None if absent).
    `symbols` collects event-facing names: type structs, Filter*/Watch*/Parse*
    helpers and iterators found in the file.
    """
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    m = _META_RE.search(src)
    name = m.group(1) if m else None
    abi = None
    if m:
        idx = src.find("ABI:", m.end())
        if idx != -1:
            q = src.find('"', idx)
            raw, _ = _go_string_literal(src, q)
            try:
                abi = json.loads(raw)
            except json.JSONDecodeError:
                abi = None
    events = sorted(set(re.findall(r"type\s+(" + (name or r"\w+") + r"\w*(?:Iterator|Session|Filterer)\b)", src)))
    filterers = sorted(set(re.findall(r"type\s+(\w+Filterer)\b", src)))
    fns = sorted(set(re.findall(r"func\s+\([^)]*\)\s+(\w+)\(", src)) | set(re.findall(r"func\s+(\w+)\(", src)))
    structs = sorted(set(re.findall(r"type\s+(\w+)\s+struct\b", src)))
    return {
        "contract": name,
        "abi": abi,
        "bin_present": "Bin:" in src[m.start():m.start() + 100000] if m else False,
        "event_filterers": filterers or events,
        "structs": structs,
        "functions": fns,
    }


def binding_event_names(parsed):
    """Event names derivable from a parsed binding: structs like <C><E>Event
    are not abigen's convention; abigen emits `<C><E>Iterator` and methods
    `Filter<E>/Watch<E>/Parse<E>` on the Filterer plus `<C><E>` event structs
    named after the event. We return every capitalised identifier that follows
    the contract prefix in event helper symbols."""
    c = parsed.get("contract") or ""
    names = set()
    for s in parsed.get("structs", []):
        if c and s.startswith(c) and len(s) > len(c):
            names.add(s[len(c):])
    for s in parsed.get("event_filterers", []):
        for pre in ("Filter", "Watch", "Parse"):
            for fn in parsed.get("functions", []):
                if fn.startswith(pre) and len(fn) > len(pre):
                    names.add(fn[len(pre):])
    return sorted(names)
