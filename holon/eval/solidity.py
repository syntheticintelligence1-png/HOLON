"""The Solidity side of the renaming tool (I48 rules N1-N3): the pinned solc 0.8.24 run with --stop-after parsing on
a copy whose version pragmas are neutralised, for the declared, ABI-visible and override names, and the normalised AST
of rule N3. The lexer is holon.eval.sollex (it works on the file's bytes, so its offsets are byte offsets and a file
that is not valid UTF-8 round-trips unchanged).
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from . import common, sollex


# ------------------------------------------------------------------------------------------------- pragmas
def neutralise(src: bytes) -> bytes:
    """The bytes solc parses (rule N3): every `pragma solidity <expr>;` (pragma directly followed by solidity, up to
    the next ; token) becomes `pragma solidity >=0.0.0;` (solc 0.8.24 refuses an unsatisfied version pragma even
    when it stops after parsing)."""
    toks = sollex.lex(src)
    parts, last = [], 0
    for i, (k, s, e) in enumerate(toks):
        if k != "id" or src[s:e] != b"pragma" or s < last or i + 1 >= len(toks):
            continue
        k2, s2, e2 = toks[i + 1]
        if k2 != "id" or src[s2:e2] != b"solidity":
            continue
        semi = next(((s3, e3) for k3, s3, e3 in toks[i + 2:] if k3 == "op" and src[s3:e3] == b";"), None)
        if semi is not None:
            parts += [src[last:s], b"pragma solidity >=0.0.0;"]
            last = semi[1]
    parts.append(src[last:])
    return b"".join(parts)


# ------------------------------------------------------------------------------------------------- solc
def _holon_config() -> dict:
    return common.load_json(common.ROOT / "config" / "holon.json").get("replay", {})


def solc_path() -> Path | None:
    """The pinned solc 0.8.24: the first existing of $HOLON_SOLC, config/holon.json replay.solc and
    ~/.holon/solc-0.8.24 (tools/setup_env.sh --solc); its sha256 must be replay.solc_sha256. None when none exists."""
    cfg = _holon_config()
    for c in (os.environ.get("HOLON_SOLC"), cfg.get("solc"), str(Path.home() / ".holon" / "solc-0.8.24")):
        if c and Path(c).is_file():
            if common.sha256_file(c) != cfg["solc_sha256"]:
                raise common.Refused(f"{c} is not the pinned solc 0.8.24 (sha256 differs from replay.solc_sha256)")
            return Path(c)
    return None


def require_solc() -> Path:
    exe = solc_path()
    if exe is None:
        raise common.Refused("the pinned solc 0.8.24 is missing (rule N1 (e) needs it): run tools/setup_env.sh --solc "
                             "or set HOLON_SOLC")
    return exe


def parse(src: bytes, exe: Path | None = None):
    """solc's parse-only AST (compact JSON) of the neutralised bytes, or None when solc cannot parse them."""
    exe = exe or require_solc()
    with tempfile.TemporaryDirectory(prefix="holon-solc-") as tmp:
        (Path(tmp) / "Input.sol").write_bytes(neutralise(src))
        p = subprocess.run([str(exe), "--stop-after", "parsing", "--ast-compact-json", "Input.sol"], cwd=tmp,
                           capture_output=True, timeout=600)
    if p.returncode != 0:
        return None
    text = p.stdout.decode("utf-8", errors="surrogateescape")
    head = "======= Input.sol =======\n"
    at = text.find(head)
    if at < 0:
        return None
    return json.loads(text[at + len(head):])


_DECLARING = {"ContractDefinition", "FunctionDefinition", "ModifierDefinition", "VariableDeclaration",
              "StructDefinition", "EnumDefinition", "EnumValue", "UserDefinedValueTypeDefinition", "EventDefinition",
              "ErrorDefinition", "YulTypedName", "YulFunctionDefinition"}


def ast_names(tree) -> dict:
    """What rule N1 reads from a parse-only AST: decls (every declared name: contracts, interfaces and libraries,
    functions, modifiers, variables, parameters and struct members, structs, enums and their values, user-defined
    value types, events, errors, import aliases, Yul variables and functions), abi (public or external functions,
    variables declared public, events, errors) and override (functions and modifiers with an override specifier)."""
    decls, abi, over = set(), set(), set()
    stack = [tree]
    while stack:
        x = stack.pop()
        if isinstance(x, list):
            stack.extend(x)
            continue
        if not isinstance(x, dict):
            continue
        kind, name = x.get("nodeType"), x.get("name")
        named = isinstance(name, str) and name != ""
        if kind in _DECLARING and named:
            decls.add(name)
        if kind == "ImportDirective":
            for a in x.get("symbolAliases") or []:
                if a.get("local"):
                    decls.add(a["local"])
            if x.get("unitAlias"):
                decls.add(x["unitAlias"])
        if named and ((kind == "FunctionDefinition" and x.get("visibility") in ("public", "external"))
                      or (kind == "VariableDeclaration" and x.get("visibility") == "public")
                      or kind in ("EventDefinition", "ErrorDefinition")):
            abi.add(name)
        if named and kind in ("FunctionDefinition", "ModifierDefinition") and x.get("overrides") is not None:
            over.add(name)
        stack.extend(x.values())
    return {"decls": decls, "abi": abi, "override": over}


# ------------------------------------------------------------------------------------------------- self-check (N3)
# Fields of a parse-only AST that are positions, node ids, references or comments; everything else is structure.
_POSITIONAL = {"src", "nativeSrc", "id", "documentation", "license", "absolutePath", "referencedDeclaration", "scope",
               "overloadedDeclarations", "assignments", "exportedSymbols", "contractDependencies", "usedErrors",
               "usedEvents", "linearizedBaseContracts", "baseFunctions", "externalReferences",
               "functionReturnParameters"}
# String fields that hold a name (or a dotted path of names, or a list of names).
_NAME_FIELDS = {"name", "memberName", "names", "local", "unitAlias", "keyName", "valueName", "errorName",
                "functionName", "eventName"}


def normal_ast(tree, idmap: dict | None = None):
    """The AST as the tool's self-check compares it: positions, ids, references and comments dropped, every name
    field mapped through idmap (each dot-separated part)."""
    m = idmap or {}

    def go(x, key=None):
        if isinstance(x, dict):
            return {k: go(v, k) for k, v in x.items()
                    if k not in _POSITIONAL and not k.endswith("Location") and not k.endswith("Locations")}
        if isinstance(x, list):
            return [go(v, key) for v in x]
        if isinstance(x, str) and key in _NAME_FIELDS:
            return ".".join(m.get(part, part) for part in x.split("."))
        return x
    return go(tree)
