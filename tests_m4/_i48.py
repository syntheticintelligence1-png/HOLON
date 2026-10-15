"""Shared preregistered I48 contract helpers. No oracle or outcome generation."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from collections import namedtuple

ROOT = Path(__file__).resolve().parents[1]
INSTRUMENT = ROOT / "spec/M4/lib/I48/instrument.json"
SHA = re.compile(r"[0-9a-f]{40}\Z")


def load(path: str | Path) -> dict:
    file = ROOT / path
    assert file.is_file(), f"Missing build outcome: {file}"
    return json.loads(file.read_text())


def instrument() -> dict:
    return load(INSTRUMENT)


def inside(path: str, directory: str) -> Path:
    target = (ROOT / path).resolve()
    assert target.is_relative_to((ROOT / directory).resolve()), path
    return target


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)


def corpus() -> list[dict]:
    data = load("spec/eval/corpus.json")
    assert isinstance(data["defects"], list)
    return data["defects"]


def check_bundle_syntax(language: str, files: list[Path]) -> None:
    """Execute the real parser on every source, including renamed sources."""
    assert files, "Empty source bundle"
    for file in files:
        assert file.is_file(), file
        if language == "go":
            assert file.suffix == ".go"
            result = subprocess.run(["gofmt", "-e", str(file)], capture_output=True, check=False)
        elif language == "solidity":
            assert file.suffix == ".sol" and file.stat().st_size
            tokens = lex_source(file.read_text(), language)
            assert any(value in {"contract", "library", "interface", "function"}
                       for kind, value in tokens if kind == "id"), file
            stack = []
            for kind, value in tokens:
                if kind in {"comment", "string"}:
                    continue
                if value in "{([":
                    stack.append(value)
                elif value in "})]":
                    assert stack and stack.pop() == {"}": "{", ")": "(", "]": "["}[value], file
            assert not stack, file
            result = subprocess.run(
                ["/home/factory-user/.holon/solc-0.8.24", "--stop-after", "parsing",
                 "--base-path", str(file.parent), "--include-path", str(file.parent), str(file)],
                capture_output=True, check=False)
        else:
            raise AssertionError(f"Unsupported language: {language}")
        assert result.returncode == 0, (file, result.stderr.decode(errors="replace"))
        if language == "go":
            assert not result.stderr.strip(), (file, result.stderr.decode(errors="replace"))


TOKEN = re.compile(
    r"(?P<space>\s+)|(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)|"
    r"(?P<string>\"(?:\\.|[^\"\\])*\"|`[^`]*`|'(?:\\.|[^'\\])*')|"
    r"(?P<id>[A-Za-z_$][A-Za-z_0-9$]*)|(?P<number>0[xX][0-9a-fA-F]+|\d+)|"
    r"(?P<op>:=|=>|->|==|!=|<=|>=|\+\+|--|&&|\|\||\+=|-=|<<|>>|.)"
)
KEYWORDS = set("""package import func type var const struct interface map chan go defer return
if else for range switch case default break continue select fallthrough true false nil
int int8 int16 int32 int64 uint uint8 uint16 uint32 uint64 uintptr byte rune bool string
error any make new append len cap copy delete close panic recover iota
pragma solidity contract library function modifier event mapping enum address payable
public private internal external view pure returns memory storage calldata indexed
virtual override immutable constant constructor receive fallback emit revert require assert
bytes bytes1 bytes2 bytes4 bytes8 bytes16 bytes20 bytes32 uint256 uint128 uint64
int256 int128 msg tx block this super abi unchecked assembly using is as
context Context""".split())
DECL = {"func", "type", "var", "const", "contract", "library", "interface",
        "struct", "event", "error", "function", "modifier", "enum"}
Signature = namedtuple("Signature", "token_skeleton scope_bindings")


def lex_source(source: str, language: str) -> list[tuple[str, str]]:
    assert language in {"go", "solidity"}
    tokens = []
    offset = 0
    for match in TOKEN.finditer(source):
        assert match.start() == offset, "Unlexed source"
        offset = match.end()
        tokens.append((match.lastgroup, match.group()))
    assert offset == len(source)
    return tokens


def extract_comments_and_strings(source: str) -> list[tuple[str, str]]:
    return [(kind, value) for kind, value in lex_source(source, "go")
            if kind in {"comment", "string"}]


def reference_binding_signature(source: str, language: str) -> Signature:
    """Independent lexical binding graph; identifiers are resolved by nearest block.

    This is deliberately kept in the acceptance tests, not imported from the
    implementation. Unknown identifiers retain their spelling as free names.
    """
    tokens = [(k, v) for k, v in lex_source(source, language)
              if k not in {"space", "comment"}]
    scopes: list[dict[str, tuple]] = [{}]
    free_bindings: dict[str, tuple] = {}
    paths = [()]
    children: dict[tuple, int] = {}
    declarations = []
    skeleton = []
    pending_params: list[tuple[str, tuple]] = []
    # Mark parameter declarations before walking uses. Parameter names are
    # bound in the immediately following body, not the containing file scope.
    parameter_positions = set()
    for start, (_, word) in enumerate(tokens):
        if word not in {"func", "function", "modifier", "constructor"}:
            continue
        opening = next((i for i in range(start + 1, len(tokens))
                        if tokens[i][1] == "("), None)
        if opening is None:
            continue
        depth = 1
        for i in range(opening + 1, len(tokens)):
            v = tokens[i][1]
            depth += (v == "(") - (v == ")")
            if depth == 0:
                break
            if depth == 1 and tokens[i][0] == "id" and v not in KEYWORDS:
                before = tokens[i - 1][1]
                after = tokens[i + 1][1] if i + 1 < len(tokens) else ""
                if ((language == "go" and after not in {",", ")"}) or
                    (language == "solidity" and before in
                     {"uint", "uint256", "address", "bytes32", "string", "memory", "calldata"})):
                    parameter_positions.add(i)
    for pos, (kind, value) in enumerate(tokens):
        previous = tokens[pos - 1][1] if pos else ""
        following = tokens[pos + 1][1] if pos + 1 < len(tokens) else ""
        if value == "{":
            parent = paths[-1]
            index = children.get(parent, 0)
            children[parent] = index + 1
            paths.append(parent + (index,))
            scopes.append({})
            for name, binding in pending_params:
                scopes[-1][name] = binding
            pending_params.clear()
        if kind == "id" and value not in KEYWORDS:
            is_decl = pos in parameter_positions or previous in DECL or following == ":=" or (
                language == "solidity" and previous in {"uint", "uint256", "address", "bytes32", "string"})
            if is_decl:
                target_path = paths[-1]
                if pos in parameter_positions:
                    target_path += (children.get(paths[-1], 0),)
                binding = (target_path, len([d for d in declarations if d[0] == target_path]))
                if pos in parameter_positions:
                    pending_params.append((value, binding))
                else:
                    scopes[-1][value] = binding
                declarations.append((target_path, binding[1], value))
            else:
                binding = next((s[value] for s in reversed(scopes) if value in s), None)
                if binding is None:
                    binding = free_bindings.setdefault(value, ("free", len(free_bindings)))
            skeleton.append(("binding", binding))
        else:
            skeleton.append((kind, value))
        if value == "}":
            assert len(scopes) > 1, "Unmatched brace"
            scopes.pop()
            paths.pop()
    assert len(scopes) == 1, "Unmatched brace"
    return Signature(tuple(skeleton), tuple(declarations))
