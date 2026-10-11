"""AST loading for the Solidity frontend.

Runs solc --ast-compact-json over the spec's source files (caching the .ast
files outside the repo) and builds the node index the translator walks.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

DEFAULT_SOLC = os.environ.get("HOLON_SOLC") or str(Path.home() / ".holon" / "solc-0.8.24")


class Unit:
    """One compiled Solidity source unit (a .sol file's AST)."""

    def __init__(self, node, path):
        self.node = node            # SourceUnit node
        self.path = path            # solc absolutePath (relative to base_path)
        self.nodes = {}             # id -> node
        self.file_lines = None      # lazy
        self._index(node)

    def _index(self, n):
        if isinstance(n, dict):
            i = n.get("id")
            if i is not None:
                self.nodes[i] = n
            for v in n.values():
                self._index(v)
        elif isinstance(n, list):
            for v in n:
                self._index(v)

    def find(self, node_type, **attrs):
        out = []
        for n in self.nodes.values():
            if n.get("nodeType") == node_type and all(n.get(k) == v for k, v in attrs.items()):
                out.append(n)
        return out


class AstWorld:
    """All units of one compilation + source-position utilities."""

    def __init__(self, units, morph_root, base_path, repo_prefix):
        self.units = units                      # solc path -> Unit
        self.morph_root = Path(morph_root)
        self.base_path = base_path              # relative to morph_root
        self.repo_prefix = repo_prefix          # prefix prepended to solc paths -> repo path
        self._line_maps = {}

    def repo_path(self, solc_path):
        return self.repo_prefix + solc_path if not solc_path.startswith("@") else solc_path

    def srcpos(self, node):
        """-> (repo_path, line) for a node's src "off:len:file" (file ignored: units parsed separately)."""
        off = int(node["src"].split(":")[0])
        return node.get("__file"), self._line_of(node.get("__file"), off)

    def _line_of(self, solc_path, offset):
        if solc_path not in self._line_maps:
            if solc_path.startswith("@"):
                p = self.morph_root / self.base_path / "node_modules" / solc_path
            else:
                p = self.morph_root / self.base_path / solc_path
            starts = [0]
            try:
                data = p.read_text()
                for i, ch in enumerate(data):
                    if ch == "\n":
                        starts.append(i + 1)
            except OSError:
                data = ""
            self._line_maps[solc_path] = (data, starts)
        data, starts = self._line_maps[solc_path]
        # binary search
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    def line(self, node):
        off = int(node["src"].split(":")[0])
        return self._line_of(node["__file"], off)

    def line_end(self, node):
        off, ln = node["src"].split(":")[:2]
        return self._line_of(node["__file"], int(off) + int(ln))


def _tag_file(n, fname):
    if isinstance(n, dict):
        n["__file"] = fname
        for v in n.values():
            _tag_file(v, fname)
    elif isinstance(n, list):
        for v in n:
            _tag_file(v, fname)


def run_solc(spec, morph_root, solc=None, cache_dir=None):
    """Invoke solc --ast-compact-json for all spec sources; return {solc_path: ast_json}."""
    solc = solc or DEFAULT_SOLC
    if shutil.which(solc) is None and not os.path.exists(solc):
        raise RuntimeError(f"solc not found: {solc} (set HOLON_SOLC)")
    morph_root = Path(morph_root)
    base = spec.get("base_path", "contracts")
    cache_dir = Path(cache_dir or (Path.home() / ".holon" / "cache" / "m2" / "ast"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    srcs = [s for s in spec["contracts"] if not s.startswith("@")]
    out_dir = cache_dir / "ast"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    workdir = morph_root / base
    inc = spec.get("include_path", "node_modules")
    if inc.startswith(base + "/"):
        inc = inc[len(base) + 1:]
    cmd = [solc, "--ast-compact-json"] + srcs + [
        "--base-path", ".",
        "--include-path", inc,
        "--evm-version", spec.get("solc", {}).get("evm_version", "cancun"),
        "-o", str(out_dir),
    ]
    r = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("solc failed:\n" + r.stderr[-4000:])
    units = {}
    for f in sorted(out_dir.glob("*_json.ast")):
        ast = json.loads(f.read_text())
        s = ast.get("absolutePath")
        if s is None:
            continue
        _tag_file(ast, s)
        units[s] = Unit(ast, s)
    return AstWorld(units, morph_root, base, spec.get("repo_prefix", ""))
