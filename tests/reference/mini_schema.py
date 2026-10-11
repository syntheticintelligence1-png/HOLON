"""Minimal JSON Schema validator for the subset used in schemas/ (frozen oracle).

Supports: type, required, properties, additionalProperties (bool or schema), enum,
const, pattern, items, minItems, maxItems, oneOf, allOf, if/then, $ref "#/$defs/..".
Used so the tests need nothing outside the Python standard library. If the
`jsonschema` package is installed, tests also cross-check with it.
"""
from __future__ import annotations

import re

_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "integer": int, "number": (int, float), "null": type(None),
}


class SchemaError(Exception):
    pass


def _is_type(v, t: str) -> bool:
    if t in ("integer", "number") and isinstance(v, bool):
        return False
    return isinstance(v, _TYPES[t])


def errors(instance, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    root = root or schema
    out: list[str] = []
    if "$ref" in schema:
        ref = schema["$ref"]
        assert ref.startswith("#/"), ref
        target = root
        for part in ref[2:].split("/"):
            target = target[part]
        return errors(instance, target, root, path)
    if "type" in schema:
        ts = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(instance, t) for t in ts):
            return [f"{path}: expected type {ts}, got {type(instance).__name__}"]
    if "const" in schema and instance != schema["const"]:
        out.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        out.append(f"{path}: {instance!r} not in {schema['enum']}")
    if "pattern" in schema and isinstance(instance, str) and not re.search(schema["pattern"], instance):
        out.append(f"{path}: {instance!r} does not match {schema['pattern']}")
    if isinstance(instance, dict):
        for k in schema.get("required", []):
            if k not in instance:
                out.append(f"{path}: missing required key {k!r}")
        props = schema.get("properties", {})
        for k, v in instance.items():
            if k in props:
                out.extend(errors(v, props[k], root, f"{path}.{k}"))
            else:
                ap = schema.get("additionalProperties", True)
                if ap is False:
                    out.append(f"{path}: unexpected key {k!r}")
                elif isinstance(ap, dict):
                    out.extend(errors(v, ap, root, f"{path}.{k}"))
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            out.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            out.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, v in enumerate(instance):
                out.extend(errors(v, schema["items"], root, f"{path}[{i}]"))
    if "oneOf" in schema:
        n = sum(1 for s in schema["oneOf"] if not errors(instance, s, root, path))
        if n != 1:
            out.append(f"{path}: matches {n} of oneOf alternatives (need exactly 1)")
    for s in schema.get("allOf", []):
        if "if" in s:
            if not errors(instance, s["if"], root, path):
                out.extend(errors(instance, s.get("then", {}), root, path))
        else:
            out.extend(errors(instance, s, root, path))
    return out


def validate(instance, schema: dict) -> None:
    errs = errors(instance, schema)
    if errs:
        raise SchemaError("; ".join(errs[:10]))
    try:  # optional cross-check
        import jsonschema  # type: ignore
        jsonschema.validate(instance, schema)
    except ImportError:
        pass
