"""A small JSON Schema validator for the subset HOLON's schemas use (gate G9).

holon/ may not use the frozen test oracle (AGENTS.md rule 5), so the gate carries its
own validator, written independently. Supported keywords: type, required, properties, additionalProperties
(bool or schema), enum, const, pattern, items, minItems, maxItems, oneOf, allOf (with
if/then), $ref to "#/$defs/..." or "#/definitions/...". Unknown keywords are ignored,
as JSON Schema prescribes; schemas that rely on others must not be validated here.
"""
from __future__ import annotations

import re

_PY = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _has_type(v, t: str) -> bool:
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _PY[t])


def _deref(schema: dict, root: dict) -> dict:
    while "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            raise ValueError(f"unsupported $ref {ref}")
        node = root
        for part in ref[2:].split("/"):
            node = node[part]
        schema = node
    return schema


def errors(value, schema: dict, root: dict | None = None, at: str = "$") -> list[str]:
    root = schema if root is None else root
    schema = _deref(schema, root)
    out: list[str] = []
    if "type" in schema:
        ts = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_has_type(value, t) for t in ts):
            return [f"{at}: not of type {ts}"]
    if "const" in schema and value != schema["const"]:
        out.append(f"{at}: != {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{at}: {value!r} not one of {schema['enum']}")
    if "pattern" in schema and isinstance(value, str) and re.search(schema["pattern"], value) is None:
        out.append(f"{at}: {value!r} does not match {schema['pattern']!r}")
    if isinstance(value, dict):
        out += [f"{at}: missing {k!r}" for k in schema.get("required", []) if k not in value]
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for k in sorted(value):
            if k in props:
                out += errors(value[k], props[k], root, f"{at}.{k}")
            elif extra is False:
                out.append(f"{at}: unexpected key {k!r}")
            elif isinstance(extra, dict):
                out += errors(value[k], extra, root, f"{at}.{k}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            out.append(f"{at}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            out.append(f"{at}: more than {schema['maxItems']} items")
        if isinstance(schema.get("items"), dict):
            for i, x in enumerate(value):
                out += errors(x, schema["items"], root, f"{at}[{i}]")
    if "oneOf" in schema:
        n = sum(not errors(value, s, root, at) for s in schema["oneOf"])
        if n != 1:
            out.append(f"{at}: matches {n} oneOf alternatives, not exactly one")
    for s in schema.get("allOf", []):
        if "if" in s:
            if not errors(value, s["if"], root, at):
                out += errors(value, s.get("then", {}), root, at)
        else:
            out += errors(value, s, root, at)
    return out
