"""Deterministic, seed-parameterized bijective isomorphic renaming for evaluation."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

SOLIDITY_RESERVED = frozenset(
    {
        "abstract",
        "address",
        "after",
        "alias",
        "anonymous",
        "apply",
        "as",
        "assembly",
        "assert",
        "auto",
        "bool",
        "break",
        "byte",
        "bytes",
        "calldata",
        "case",
        "catch",
        "constant",
        "constructor",
        "continue",
        "contract",
        "copyof",
        "days",
        "default",
        "define",
        "delete",
        "do",
        "else",
        "emit",
        "enum",
        "error",
        "ether",
        "event",
        "external",
        "fallback",
        "false",
        "final",
        "fixed",
        "for",
        "from",
        "function",
        "gasleft",
        "global",
        "gwei",
        "hours",
        "if",
        "immutable",
        "implements",
        "import",
        "in",
        "indexed",
        "inline",
        "int",
        "interface",
        "internal",
        "is",
        "keccak256",
        "let",
        "library",
        "macro",
        "mapping",
        "match",
        "memory",
        "minutes",
        "modifier",
        "mutable",
        "new",
        "null",
        "of",
        "override",
        "partial",
        "payable",
        "pragma",
        "private",
        "promise",
        "public",
        "pure",
        "receive",
        "reference",
        "relocatable",
        "require",
        "return",
        "returns",
        "revert",
        "ripemd160",
        "sealed",
        "seconds",
        "selfdestruct",
        "sha256",
        "sizeof",
        "solidity",
        "static",
        "storage",
        "string",
        "struct",
        "super",
        "supports",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "type",
        "typedef",
        "typeof",
        "ufixed",
        "uint",
        "unchecked",
        "unicode",
        "using",
        "var",
        "view",
        "virtual",
        "weeks",
        "wei",
        "while",
        "years",
        "msg",
        "sender",
        "value",
        "data",
        "sig",
        "block",
        "timestamp",
        "number",
        "chainid",
        "coinbase",
        "basefee",
        "prevrandao",
        "gaslimit",
        "tx",
        "origin",
        "gasprice",
        "abi",
        "encode",
        "encodePacked",
        "encodeWithSelector",
        "encodeWithSignature",
        "encodeCall",
        "decode",
        "ecrecover",
        "addmod",
        "mulmod",
        "max",
        "min",
    }
    | {f"uint{w}" for w in range(8, 264, 8)}
    | {f"int{w}" for w in range(8, 264, 8)}
    | {f"bytes{w}" for w in range(1, 33)}
)

GO_RESERVED = frozenset(
    {
        "any",
        "append",
        "bool",
        "break",
        "byte",
        "cap",
        "case",
        "chan",
        "clear",
        "close",
        "comparable",
        "complex",
        "complex64",
        "complex128",
        "const",
        "continue",
        "copy",
        "default",
        "defer",
        "delete",
        "else",
        "error",
        "fallthrough",
        "false",
        "float32",
        "float64",
        "for",
        "func",
        "go",
        "goto",
        "if",
        "imag",
        "import",
        "int",
        "int8",
        "int16",
        "int32",
        "int64",
        "interface",
        "iota",
        "len",
        "make",
        "map",
        "max",
        "min",
        "new",
        "nil",
        "package",
        "panic",
        "print",
        "println",
        "range",
        "real",
        "recover",
        "return",
        "rune",
        "select",
        "string",
        "struct",
        "switch",
        "true",
        "type",
        "uint",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "uintptr",
        "var",
    }
)

FACTS_RESERVED_VALUES = frozenset(
    {
        "holon-facts/0.1",
        "holon-facts/0.2",
        "holon-ir/0.1",
        "holon-ir/0.2",
        "holon-ir/0.3",
        "holon-rules/0.1",
        "holon-rules/0.2",
        "Nat",
        "Bool",
        "State",
        "Reach",
        "Trace",
        "Act",
        "Obs",
        "List<Nat>",
        "List<Obs>",
        "log",
        "any",
        "forall",
        "exists",
        "unbounded",
        "bounded",
        "at_state",
        "PAR",
        "SORT",
        "NAT",
        "OWN",
        "DISCH",
        "FACT",
        "UNDO",
        "SYM",
        "+",
        "-",
        "==",
        "!=",
        "<",
        "<=",
        ">",
        ">=",
        "!",
        "&&",
        "||",
        "?",
        "call",
        "get",
        "mk",
        "with",
        "list",
        "len",
        "take",
        "drop",
        "tail",
        "concat",
        "snoc",
        "eq_nats",
        "nth",
        "set_nat",
        "mem",
        "remove",
        "zeros_like",
        "eq_nat",
        "eq_bool",
        "last_ok",
        "runs_ok",
        "no_code",
        "perm",
        "cost",
        "elapsed",
    }
)

_TOKEN_RE = re.compile(
    r"(?P<block_comment>/\*[\s\S]*?\*/)"
    r"|(?P<line_comment>//[^\n]*)"
    r"|(?P<raw_str>`[^`]*`)"
    r'|(?P<dquote_str>"(?:\\.|[^"\\])*")'
    r"|(?P<squote_str>'(?:\\.|[^'\\])*')"
    r"|(?P<number>\b(?:0[xX][0-9a-fA-F_]+|\d[0-9a-fA-F_.]*)\b)"
    r"|(?P<ident>[A-Za-z_$][A-Za-z0-9_$]*)"
)

_IDENT_FULL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _reserved_for(language: str) -> frozenset[str]:
    lang = language.lower().strip()
    if lang == "solidity":
        return SOLIDITY_RESERVED
    if lang == "go":
        return GO_RESERVED
    raise ValueError(f"unsupported language: {language!r}")


def _make_alias(ident: str, seed: int, index: int, used: set[str]) -> str:
    salt = 0
    while True:
        digest = hashlib.sha256(f"holon-rename:{seed}:{index}:{salt}:{ident}".encode("utf-8")).hexdigest()
        candidate = f"id_{digest[:10]}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        salt += 1


def validate_mapping(mapping: dict) -> bool:
    """Validate that `mapping` defines a collision-free bijection between original and renamed identifiers."""
    if not isinstance(mapping, dict):
        raise ValueError("mapping must be a dict")
    forward = mapping.get("forward")
    reverse = mapping.get("reverse")
    if not isinstance(forward, dict) or not isinstance(reverse, dict):
        raise ValueError("mapping must contain 'forward' and 'reverse' dicts")
    seen_targets: set[str] = set()
    for src_id, dst_id in forward.items():
        if not isinstance(src_id, str) or not src_id or not isinstance(dst_id, str) or not dst_id:
            raise ValueError("mapping identifiers must be non-empty strings")
        if dst_id in seen_targets:
            raise ValueError(f"non-bijective forward mapping: duplicate target identifier {dst_id!r}")
        seen_targets.add(dst_id)
    expected_reverse = {dst_id: src_id for src_id, dst_id in forward.items()}
    if reverse != expected_reverse:
        raise ValueError("reverse mapping does not match inverse of forward mapping")
    for section in ("comments", "strings"):
        sec = mapping.get(section, {})
        if not isinstance(sec, dict):
            raise ValueError(f"mapping section {section!r} must be a dict")
    return True


def rename(src: str, language: str = "solidity", seed: int = 0) -> tuple[str, dict]:
    """Deterministically scrub comments/strings and bijectively rename non-reserved identifiers."""
    reserved = _reserved_for(language)
    existing_tokens = set(re.findall(r"[A-Za-z_$][A-Za-z0-9_$]*", src))
    used_aliases: set[str] = set(existing_tokens) | set(reserved)

    forward: dict[str, str] = {}
    comments: dict[str, str] = {}
    strings: dict[str, str] = {}
    out_parts: list[str] = []
    last_end = 0
    cmt_idx = 0
    str_idx = 0

    for m in _TOKEN_RE.finditer(src):
        out_parts.append(src[last_end : m.start()])
        last_end = m.end()
        kind = m.lastgroup
        tok = m.group(0)
        if kind == "line_comment":
            cmt_idx += 1
            tag = hashlib.sha256(f"cmt:{seed}:{cmt_idx}:{tok}".encode("utf-8")).hexdigest()[:10]
            placeholder = f"// __holon_cmt_{cmt_idx:04d}_{tag}__"
            comments[placeholder] = tok
            out_parts.append(placeholder)
        elif kind == "block_comment":
            cmt_idx += 1
            tag = hashlib.sha256(f"cmt:{seed}:{cmt_idx}:{tok}".encode("utf-8")).hexdigest()[:10]
            placeholder = f"/* __holon_cmt_{cmt_idx:04d}_{tag}__ */"
            comments[placeholder] = tok
            out_parts.append(placeholder)
        elif kind in ("raw_str", "dquote_str", "squote_str"):
            str_idx += 1
            tag = hashlib.sha256(f"str:{seed}:{str_idx}:{tok}".encode("utf-8")).hexdigest()[:10]
            quote = tok[0]
            placeholder = f"{quote}__holon_str_{str_idx:04d}_{tag}__{quote}"
            strings[placeholder] = tok
            out_parts.append(placeholder)
        elif kind == "ident":
            if tok in reserved:
                out_parts.append(tok)
            else:
                if tok not in forward:
                    forward[tok] = _make_alias(tok, seed, len(forward) + 1, used_aliases)
                out_parts.append(forward[tok])
        else:
            out_parts.append(tok)

    out_parts.append(src[last_end:])
    renamed_src = "".join(out_parts)
    reverse = {v: k for k, v in forward.items()}
    mapping = {
        "schema": "holon-rename-map/0.1",
        "language": language.lower().strip(),
        "seed": int(seed),
        "forward": forward,
        "reverse": reverse,
        "comments": comments,
        "strings": strings,
    }
    validate_mapping(mapping)
    return renamed_src, mapping


def unrename(renamed_src: str, mapping: dict) -> str:
    """Invert `rename(src, ...)` using a validated bijective `mapping`."""
    validate_mapping(mapping)
    reverse = mapping["reverse"]
    comments = mapping.get("comments", {})
    strings = mapping.get("strings", {})

    out_parts: list[str] = []
    last_end = 0
    for m in _TOKEN_RE.finditer(renamed_src):
        out_parts.append(renamed_src[last_end : m.start()])
        last_end = m.end()
        kind = m.lastgroup
        tok = m.group(0)
        if kind in ("line_comment", "block_comment"):
            out_parts.append(comments.get(tok, tok))
        elif kind in ("raw_str", "dquote_str", "squote_str"):
            out_parts.append(strings.get(tok, tok))
        elif kind == "ident":
            out_parts.append(reverse.get(tok, tok))
        else:
            out_parts.append(tok)
    out_parts.append(renamed_src[last_end:])
    return "".join(out_parts)


def _collect_strings(obj, out: set[str]) -> None:
    if isinstance(obj, str):
        if _IDENT_FULL_RE.match(obj):
            out.add(obj)
    elif isinstance(obj, list):
        for item in obj:
            _collect_strings(item, out)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and _IDENT_FULL_RE.match(k):
                out.add(k)
            _collect_strings(v, out)


def _rename_expr(expr, remap_fn):
    if isinstance(expr, str):
        if expr in FACTS_RESERVED_VALUES or not _IDENT_FULL_RE.match(expr):
            return expr
        return remap_fn(expr)
    if isinstance(expr, list):
        return [_rename_expr(x, remap_fn) for x in expr]
    if isinstance(expr, dict):
        return {
            (remap_fn(k) if isinstance(k, str) else k): _rename_expr(v, remap_fn)
            for k, v in expr.items()
        }
    return expr


def rename_facts(facts_doc: dict, seed: int = 0) -> tuple[dict, dict]:
    """Bijectively rename domain identifiers in a HOLON facts JSON document."""
    doc = copy.deepcopy(facts_doc)
    used_aliases: set[str] = set(FACTS_RESERVED_VALUES)
    _collect_strings(doc, used_aliases)
    forward: dict[str, str] = {}

    def map_id(ident: str) -> str:
        if ident in FACTS_RESERVED_VALUES or not _IDENT_FULL_RE.match(ident):
            return ident
        if ident not in forward:
            forward[ident] = _make_alias(ident, seed, len(forward) + 1, used_aliases)
        return forward[ident]

    if isinstance(doc.get("model"), str):
        doc["model"] = map_id(doc["model"])

    if isinstance(doc.get("params"), dict):
        doc["params"] = {map_id(k): v for k, v in doc["params"].items()}

    if isinstance(doc.get("types"), dict):
        new_types = {}
        for t_name, t_spec in doc["types"].items():
            t_copy = copy.deepcopy(t_spec)
            if isinstance(t_copy.get("fields"), list):
                t_copy["fields"] = [[map_id(fn), map_id(ft)] for fn, ft in t_copy["fields"]]
            new_types[map_id(t_name)] = t_copy
        doc["types"] = new_types

    if isinstance(doc.get("state"), list):
        doc["state"] = [[map_id(name), map_id(ty), *rest] for name, ty, *rest in doc["state"]]

    if isinstance(doc.get("initial"), dict):
        doc["initial"] = {map_id(k): _rename_expr(v, map_id) for k, v in doc["initial"].items()}

    if isinstance(doc.get("defs"), dict):
        new_defs = {}
        for d_name, d_spec in doc["defs"].items():
            d_copy = copy.deepcopy(d_spec)
            if isinstance(d_copy.get("params"), list):
                d_copy["params"] = [[map_id(pn), map_id(pt)] for pn, pt in d_copy["params"]]
            if isinstance(d_copy.get("ret"), str):
                d_copy["ret"] = map_id(d_copy["ret"])
            if "body" in d_copy:
                d_copy["body"] = _rename_expr(d_copy["body"], map_id)
            new_defs[map_id(d_name)] = d_copy
        doc["defs"] = new_defs

    if isinstance(doc.get("actions"), list):
        new_actions = []
        for act in doc["actions"]:
            act_copy = copy.deepcopy(act)
            if isinstance(act_copy.get("name"), str):
                act_copy["name"] = map_id(act_copy["name"])
            if isinstance(act_copy.get("principal"), str):
                act_copy["principal"] = map_id(act_copy["principal"])
            if isinstance(act_copy.get("inputs"), list):
                act_copy["inputs"] = [[map_id(n), map_id(t), *rest] for n, t, *rest in act_copy["inputs"]]
            if isinstance(act_copy.get("guards"), list):
                new_guards = []
                for g in act_copy["guards"]:
                    g_copy = copy.deepcopy(g)
                    if "let" in g_copy and isinstance(g_copy["let"], str):
                        g_copy["let"] = map_id(g_copy["let"])
                    if "expr" in g_copy:
                        g_copy["expr"] = _rename_expr(g_copy["expr"], map_id)
                    if "require" in g_copy:
                        g_copy["require"] = _rename_expr(g_copy["require"], map_id)
                    new_guards.append(g_copy)
                act_copy["guards"] = new_guards
            if isinstance(act_copy.get("effects"), dict):
                act_copy["effects"] = {
                    map_id(k): _rename_expr(v, map_id) for k, v in act_copy["effects"].items()
                }
            new_actions.append(act_copy)
        doc["actions"] = new_actions

    if isinstance(doc.get("observers"), dict):
        new_obs = {}
        for ob_name, ob_spec in doc["observers"].items():
            ob_copy = copy.deepcopy(ob_spec)
            if isinstance(ob_copy.get("type"), str):
                ob_copy["type"] = map_id(ob_copy["type"])
            if "body" in ob_copy:
                ob_copy["body"] = _rename_expr(ob_copy["body"], map_id)
            new_obs[map_id(ob_name)] = ob_copy
        doc["observers"] = new_obs

    if isinstance(doc.get("migrations"), dict):
        new_migs = {}
        for m_name, m_spec in doc["migrations"].items():
            m_copy = copy.deepcopy(m_spec)
            if isinstance(m_copy.get("inputs"), list):
                m_copy["inputs"] = [[map_id(n), map_id(t), *rest] for n, t, *rest in m_copy["inputs"]]
            if isinstance(m_copy.get("effects"), dict):
                m_copy["effects"] = {
                    map_id(k): _rename_expr(v, map_id) for k, v in m_copy["effects"].items()
                }
            new_migs[map_id(m_name)] = m_copy
        doc["migrations"] = new_migs

    mapping = {
        "schema": "holon-rename-map/0.1",
        "language": "facts",
        "seed": int(seed),
        "forward": forward,
        "reverse": {v: k for k, v in forward.items()},
        "comments": {},
        "strings": {},
    }
    validate_mapping(mapping)
    return doc, mapping


def unrename_facts(renamed_doc: dict, mapping: dict) -> dict:
    """Invert `rename_facts` using a validated bijective `mapping`."""
    validate_mapping(mapping)
    reverse = mapping["reverse"]
    doc = copy.deepcopy(renamed_doc)

    def unmap_id(ident: str) -> str:
        return reverse.get(ident, ident)

    if isinstance(doc.get("model"), str):
        doc["model"] = unmap_id(doc["model"])

    if isinstance(doc.get("params"), dict):
        doc["params"] = {unmap_id(k): v for k, v in doc["params"].items()}

    if isinstance(doc.get("types"), dict):
        new_types = {}
        for t_name, t_spec in doc["types"].items():
            t_copy = copy.deepcopy(t_spec)
            if isinstance(t_copy.get("fields"), list):
                t_copy["fields"] = [[unmap_id(fn), unmap_id(ft)] for fn, ft in t_copy["fields"]]
            new_types[unmap_id(t_name)] = t_copy
        doc["types"] = new_types

    if isinstance(doc.get("state"), list):
        doc["state"] = [[unmap_id(name), unmap_id(ty), *rest] for name, ty, *rest in doc["state"]]

    if isinstance(doc.get("initial"), dict):
        doc["initial"] = {unmap_id(k): _rename_expr(v, unmap_id) for k, v in doc["initial"].items()}

    if isinstance(doc.get("defs"), dict):
        new_defs = {}
        for d_name, d_spec in doc["defs"].items():
            d_copy = copy.deepcopy(d_spec)
            if isinstance(d_copy.get("params"), list):
                d_copy["params"] = [[unmap_id(pn), unmap_id(pt)] for pn, pt in d_copy["params"]]
            if isinstance(d_copy.get("ret"), str):
                d_copy["ret"] = unmap_id(d_copy["ret"])
            if "body" in d_copy:
                d_copy["body"] = _rename_expr(d_copy["body"], unmap_id)
            new_defs[unmap_id(d_name)] = d_copy
        doc["defs"] = new_defs

    if isinstance(doc.get("actions"), list):
        new_actions = []
        for act in doc["actions"]:
            act_copy = copy.deepcopy(act)
            if isinstance(act_copy.get("name"), str):
                act_copy["name"] = unmap_id(act_copy["name"])
            if isinstance(act_copy.get("principal"), str):
                act_copy["principal"] = unmap_id(act_copy["principal"])
            if isinstance(act_copy.get("inputs"), list):
                act_copy["inputs"] = [[unmap_id(n), unmap_id(t), *rest] for n, t, *rest in act_copy["inputs"]]
            if isinstance(act_copy.get("guards"), list):
                new_guards = []
                for g in act_copy["guards"]:
                    g_copy = copy.deepcopy(g)
                    if "let" in g_copy and isinstance(g_copy["let"], str):
                        g_copy["let"] = unmap_id(g_copy["let"])
                    if "expr" in g_copy:
                        g_copy["expr"] = _rename_expr(g_copy["expr"], unmap_id)
                    if "require" in g_copy:
                        g_copy["require"] = _rename_expr(g_copy["require"], unmap_id)
                    new_guards.append(g_copy)
                act_copy["guards"] = new_guards
            if isinstance(act_copy.get("effects"), dict):
                act_copy["effects"] = {
                    unmap_id(k): _rename_expr(v, unmap_id) for k, v in act_copy["effects"].items()
                }
            new_actions.append(act_copy)
        doc["actions"] = new_actions

    if isinstance(doc.get("observers"), dict):
        new_obs = {}
        for ob_name, ob_spec in doc["observers"].items():
            ob_copy = copy.deepcopy(ob_spec)
            if isinstance(ob_copy.get("type"), str):
                ob_copy["type"] = unmap_id(ob_copy["type"])
            if "body" in ob_copy:
                ob_copy["body"] = _rename_expr(ob_copy["body"], unmap_id)
            new_obs[unmap_id(ob_name)] = ob_copy
        doc["observers"] = new_obs

    if isinstance(doc.get("migrations"), dict):
        new_migs = {}
        for m_name, m_spec in doc["migrations"].items():
            m_copy = copy.deepcopy(m_spec)
            if isinstance(m_copy.get("inputs"), list):
                m_copy["inputs"] = [[unmap_id(n), unmap_id(t), *rest] for n, t, *rest in m_copy["inputs"]]
            if isinstance(m_copy.get("effects"), dict):
                m_copy["effects"] = {
                    unmap_id(k): _rename_expr(v, unmap_id) for k, v in m_copy["effects"].items()
                }
            new_migs[unmap_id(m_name)] = m_copy
        doc["migrations"] = new_migs

    return doc


def _transform_law_term(term, remap_fn):
    if isinstance(term, list):
        return [_transform_law_term(x, remap_fn) for x in term]
    if not isinstance(term, dict):
        return term
    out = {}
    for k, v in term.items():
        if k in ("var", "obsv", "act", "mig", "fn", "app", "field", "call", "action") and isinstance(v, str):
            out[k] = remap_fn(v)
        elif k in ("args", "bind") and isinstance(v, dict):
            out[k] = {remap_fn(ak): _transform_law_term(av, remap_fn) for ak, av in v.items()}
        elif k == "proj" and isinstance(v, list):
            out[k] = [remap_fn(f) if isinstance(f, str) else f for f in v]
        elif k == "expr" and "from" in term:
            out[k] = _rename_expr(v, remap_fn)
        else:
            out[k] = _transform_law_term(v, remap_fn)
    return out


def rename_law(law_doc: dict, mapping: dict | None = None, seed: int = 0) -> tuple[dict, dict]:
    """Bijectively rename domain identifiers in a HOLON law IR JSON document."""
    doc = copy.deepcopy(law_doc)
    if mapping is not None:
        validate_mapping(mapping)
        forward = dict(mapping["forward"])
    else:
        forward = {}
    used_aliases: set[str] = set(FACTS_RESERVED_VALUES) | set(forward.keys()) | set(forward.values())
    _collect_strings(doc, used_aliases)

    def map_id(ident: str) -> str:
        if ident in FACTS_RESERVED_VALUES or not _IDENT_FULL_RE.match(ident):
            return ident
        if ident not in forward:
            forward[ident] = _make_alias(ident, seed, len(forward) + 1, used_aliases)
        return forward[ident]

    st = doc.get("statement")
    if isinstance(st, dict):
        if isinstance(st.get("binders"), list):
            new_binders = []
            for b in st["binders"]:
                b_copy = dict(b)
                if isinstance(b_copy.get("name"), str):
                    b_copy["name"] = map_id(b_copy["name"])
                if isinstance(b_copy.get("type"), str):
                    b_copy["type"] = map_id(b_copy["type"])
                new_binders.append(b_copy)
            st["binders"] = new_binders
        if isinstance(st.get("assume"), list):
            st["assume"] = [_transform_law_term(p, map_id) for p in st["assume"]]
        if "claim" in st:
            st["claim"] = _transform_law_term(st["claim"], map_id)

    out_map = {
        "schema": "holon-rename-map/0.1",
        "language": "law",
        "seed": int(seed),
        "forward": forward,
        "reverse": {v: k for k, v in forward.items()},
        "comments": {},
        "strings": {},
    }
    validate_mapping(out_map)
    return doc, out_map


def unrename_law(renamed_law: dict, mapping: dict) -> dict:
    """Invert `rename_law` using a validated bijective `mapping`."""
    validate_mapping(mapping)
    reverse = mapping["reverse"]
    doc = copy.deepcopy(renamed_law)

    def unmap_id(ident: str) -> str:
        return reverse.get(ident, ident)

    st = doc.get("statement")
    if isinstance(st, dict):
        if isinstance(st.get("binders"), list):
            new_binders = []
            for b in st["binders"]:
                b_copy = dict(b)
                if isinstance(b_copy.get("name"), str):
                    b_copy["name"] = unmap_id(b_copy["name"])
                if isinstance(b_copy.get("type"), str):
                    b_copy["type"] = unmap_id(b_copy["type"])
                new_binders.append(b_copy)
            st["binders"] = new_binders
        if isinstance(st.get("assume"), list):
            st["assume"] = [_transform_law_term(p, unmap_id) for p in st["assume"]]
        if "claim" in st:
            st["claim"] = _transform_law_term(st["claim"], unmap_id)

    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic bijective isomorphic renamer.")
    parser.add_argument("--input", required=True, help="Input file path.")
    parser.add_argument("--out", required=True, help="Output file path.")
    parser.add_argument("--language", default="solidity", choices=("solidity", "go", "facts", "law"))
    parser.add_argument("--seed", type=int, default=0, help="Deterministic seed.")
    parser.add_argument("--map-out", help="Output path for the bijection mapping JSON.")
    parser.add_argument("--map", dest="map_in", help="Input path for the bijection mapping JSON (for --unrename).")
    parser.add_argument("--unrename", action="store_true", help="Invert renaming using --map.")
    args = parser.parse_args(argv)

    in_path = Path(args.input)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.unrename:
        if not args.map_in:
            raise ValueError("--unrename requires --map")
        mapping = json.loads(Path(args.map_in).read_text(encoding="utf-8"))
        lang = mapping.get("language", args.language)
        raw_txt = in_path.read_text(encoding="utf-8")
        if lang == "facts":
            restored = json.dumps(unrename_facts(json.loads(raw_txt), mapping), indent=2) + "\n"
        elif lang == "law":
            restored = json.dumps(unrename_law(json.loads(raw_txt), mapping), indent=2) + "\n"
        else:
            restored = unrename(raw_txt, mapping)
        out_path.write_text(restored, encoding="utf-8")
        return 0

    raw_txt = in_path.read_text(encoding="utf-8")
    if args.language == "facts":
        renamed_doc, mapping = rename_facts(json.loads(raw_txt), seed=args.seed)
        renamed_txt = json.dumps(renamed_doc, indent=2) + "\n"
    elif args.language == "law":
        base_map = json.loads(Path(args.map_in).read_text(encoding="utf-8")) if args.map_in else None
        renamed_doc, mapping = rename_law(json.loads(raw_txt), mapping=base_map, seed=args.seed)
        renamed_txt = json.dumps(renamed_doc, indent=2) + "\n"
    else:
        renamed_txt, mapping = rename(raw_txt, language=args.language, seed=args.seed)

    out_path.write_text(renamed_txt, encoding="utf-8")
    if args.map_out:
        map_path = Path(args.map_out)
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
