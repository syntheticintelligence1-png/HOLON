"""I49 instrument: the held-out target's rules, recomputed independently of holon/ (key I49, spec/M4/predictions.json).

Written at the I49 prereg, blind: before spec/heldout/ or anything of the sealed upstream was read. Nothing here imports
holon/. What it computes, the tests compare with what holon/ writes:

  sealed_roles      the sealed file's values by role (repository, commit, source file), found by shape, since the
                    prereg does not know the sealed file's keys
  target_name       rule T1 of spec/M4/lib/heldout_protocol.json
  heldout_target    the one target whose checkout names the seal
  expected_sidecar  rules S1-S5 (S3 by a regex walk of the sealed file's direct imports, never the compiler's AST)
  expected_counts   rules V1-V5 and E1-E5 over a holon-facts/0.3 transitions document, from the document alone
  count_diagram     |V|, |E| and the per-kind counts of any written diagram
  obligations       the laws over a document in a law set, per rule and per rule/subform
  pin_changes       the files under holon/ that differ from, or are missing in, the catalog pin
  disclosures       spec/M4/lib/heldout_disclosures.jsonl, parsed
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEAL = "spec/heldout/target.json"
PROTOCOL = ROOT / "spec" / "M4" / "lib" / "heldout_protocol.json"
PIN = ROOT / "spec" / "M4" / "lib" / "heldout_catalog_pin.json"
DISCLOSURES = ROOT / "spec" / "M4" / "lib" / "heldout_disclosures.jsonl"
SIZES_SCHEMA = ROOT / "spec" / "M4" / "lib" / "sizes.schema.json"
DIAGRAM_SCHEMA = ROOT / "spec" / "M4" / "lib" / "diagram_transitions.schema.json"
TARGET_SCHEMA = ROOT / "spec" / "M4" / "lib" / "target.schema.json"
SIZES = "results/targets/sizes.json"
ROW_IDS = ["toy", "morph_m2", "morph_m3", "heldout"]
SOL_DEPS_NODE_MODULES = "node_modules"


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


# ------------------------------------------------------------------ the seal, by role
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_GH = re.compile(r"github\.com[/:]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
_OWNER_REPO = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")


def _strings(x, path=()):
    if isinstance(x, dict):
        for k in sorted(x):
            yield from _strings(x[k], path + (k,))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _strings(v, path + (i,))
    elif isinstance(x, str):
        yield path, x


def sealed_roles(d: dict) -> dict:
    """{"repo": "owner/repo", "commit": 40 hex, "source": "<path>.sol", "keys": {role: key path}} found by shape in
    the sealed file: the one 40-hex string, the one .sol path, and the one repository (a github URL, else an
    owner/repo string that is not a path to a file). Ambiguity or absence raises ValueError (a test failure)."""
    commits, sources, repos = {}, {}, {}
    for path, s in _strings(d):
        key = ".".join(map(str, path))
        if _HEX40.match(s):
            commits.setdefault(s, key)
        elif s.endswith(".sol"):
            sources.setdefault(s.lstrip("./"), key)
        m = _GH.search(s)
        if m:
            repos.setdefault(f"{m.group(1)}/{m.group(2)}", key)
    if not repos:
        for path, s in _strings(d):
            m = _OWNER_REPO.match(s)
            if m and not re.search(r"\.(sol|json|md|txt|toml|ya?ml)$", s):
                repos.setdefault(s, ".".join(map(str, path)))
    out = {}
    for role, got in (("commit", commits), ("source", sources), ("repo", repos)):
        if len(got) != 1:
            raise ValueError(f"the sealed file has {len(got)} candidate {role} values: {sorted(got)}")
        out[role] = next(iter(got))
    out["keys"] = {"commit": commits[out["commit"]], "source": sources[out["source"]], "repo": repos[out["repo"]]}
    return out


def target_name(repo: str) -> str:
    """Rule T1: the first hyphen-separated word of the owner, lowercased."""
    return repo.split("/")[0].split("-")[0].lower()


def target_names(roles: dict) -> list[str]:
    owner, name = roles["repo"].split("/")
    return sorted({target_name(roles["repo"]), owner.lower(), name.lower(), Path(roles["source"]).stem.lower()})


def heldout_target(root: Path = ROOT) -> tuple[str, dict]:
    hits = []
    for f in sorted((root / "targets").glob("*/target.json")):
        d = load(f)
        if ((d.get("checkout") or {}).get("sealed")) == SEAL:
            hits.append((f.parent.name, d))
    if len(hits) != 1:
        raise AssertionError(f"exactly one target must name the seal in checkout.sealed, found {[h[0] for h in hits]}")
    return hits[0]


# ------------------------------------------------------------------ rules S1-S5
_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_IMPORT = re.compile(r'\bimport\s+(?:[^;"\']*?\bfrom\s+)?["\']([^"\']+)["\']\s*;', re.S)
_INTERFACE = re.compile(r"\binterface\s+([A-Za-z_][A-Za-z0-9_]*)")


def code(text: str) -> str:
    return _COMMENT.sub(" ", text)


def resolve_import(unit: str, imp: str, checkout: Path, sol_deps: Path | None) -> Path | None:
    """solc's resolution with base path the checkout and include path <sol_deps>/node_modules: a ./ or ../ import is
    relative to the importing unit's directory, any other is a unit name looked up in the base path, then the
    include path."""
    if imp.startswith(("./", "../")):
        parts = []
        for p in (Path(unit).parent / imp).as_posix().split("/"):
            if p == "..":
                parts.pop()
            elif p not in ("", "."):
                parts.append(p)
        name = "/".join(parts)
    else:
        name = imp
    for base in [checkout] + ([sol_deps / SOL_DEPS_NODE_MODULES] if sol_deps else []):
        if (base / name).is_file():
            return base / name
    return None


def commit_interfaces(source: str, checkout: Path, sol_deps: Path | None) -> list[str]:
    """Rule S3: interfaces declared in a unit the sealed file imports directly, whose name ends in Verifier."""
    text = code((checkout / source).read_text(encoding="utf-8"))
    out = set()
    for imp in _IMPORT.findall(text):
        p = resolve_import(source, imp, checkout, sol_deps)
        if p is None:
            continue
        for name in _INTERFACE.findall(code(p.read_text(encoding="utf-8"))):
            if name.endswith("Verifier"):
                out.add(name)
    return sorted(out)


def expected_sidecar(roles: dict, checkout: Path, sol_deps: Path | None, solc_version: str, name: str) -> dict:
    """Rules S1-S5, but for target.scope's fixed sentence (compared separately)."""
    dev = load(ROOT / "spec" / "M2" / "lib" / "extract_rollup.json")
    stem = Path(roles["source"]).stem
    return {
        "frontend": "solidity",
        "sidecar_version": 1,
        "sources": [roles["source"]],
        "transitions": {"contract": stem, "commit_interfaces": commit_interfaces(roles["source"], checkout, sol_deps)},
        "compiler": {"version": solc_version, "settings": dev["compiler"]["settings"]},
        "target_repo": roles["repo"],
        "target_commit": roles["commit"],
        "output": f"gen/targets/{name}/facts/{stem}.extracted.json",
    }


def sidecar_view(side: dict) -> dict:
    """The fields of a written scope sidecar that rules S1-S5 decide."""
    return {"frontend": side.get("frontend"), "sidecar_version": side.get("sidecar_version"),
            "sources": side.get("sources"), "transitions": side.get("transitions"), "compiler": side.get("compiler"),
            "target_repo": (side.get("target") or {}).get("repo"),
            "target_commit": (side.get("target") or {}).get("commit"), "output": side.get("output")}


# ------------------------------------------------------------------ rules V1-V5, E1-E5
def _env_names(x, out: set) -> None:
    if isinstance(x, list):
        if len(x) == 2 and x[0] == "env" and isinstance(x[1], str):
            out.add(x[1])
        for v in x:
            _env_names(v, out)
    elif isinstance(x, dict):
        for k in sorted(x):
            _env_names(x[k], out)


def expected_counts(doc: dict) -> dict:
    """|V|, |E| and the per-kind counts the mapping gives a transitions document, from the document alone."""
    if doc.get("facts_version") != "holon-facts/0.3" or "actions" not in doc or "storage" not in doc:
        raise ValueError("not a holon-facts/0.3 transitions document")
    entries = list(doc.get("inherited_storage", [])) + list(doc["storage"])
    names = Counter(s["name"] for s in entries)
    fams = [s["name"] if names[s["name"]] == 1 else f"{s.get('declared_in') or doc.get('contract')}.{s['name']}"
            for s in entries]
    if len(set(fams)) != len(fams):
        raise ValueError("two entries of F share an id")   # rule V1 as amended before the seal opened
    names = [a["name"] for a in doc["actions"]]
    if len(set(names)) != len(names):
        raise ValueError("two actions share a name")
    env: set = set()
    _env_names(doc["actions"], env)
    ext = {c["fn"] for a in doc["actions"] for c in a.get("calls", [])}
    hashes, commits = set(), set()
    for a in doc["actions"]:
        for e in a.get("edges", []):
            if e.get("kind") == "HASH":
                hashes.add(e["fn"])
            elif e.get("kind") == "COMMIT":
                commits.add(e["fn"])
            else:
                raise ValueError(f"an edges entry of kind {e.get('kind')!r}")
    cls = Counter({"state": len(fams) + 1, "rep": 2 + len(ext) + len(commits)})
    if env:
        cls["env"] = len(env)
    if hashes:
        cls["digest"] = len(hashes)
    kinds = Counter()
    if fams:
        kinds["STORE"] = kinds["LOAD"] = len(fams)
    for a in doc["actions"]:
        if a["mutability"] in ("nonpayable", "payable"):
            kinds["TRANS"] += 1
        elif a["mutability"] in ("view", "pure"):
            kinds["LOAD"] += 1
        else:
            raise ValueError(f"action {a['name']}: mutability {a['mutability']!r}")
        if a.get("calls"):
            kinds["CALL"] += len(a["calls"])
        for e in a.get("edges", []):
            kinds[e["kind"]] += 1
    return {"V": sum(cls.values()), "E": sum(kinds.values()), "carriers_by_kind": dict(sorted(cls.items())),
            "edges_by_kind": dict(sorted((k, v) for k, v in kinds.items() if v))}


def count_diagram(d: dict) -> dict:
    cls = Counter(c["cls"] for c in d["carriers"])
    kinds = Counter(e["kind"] for e in d["edges"])
    return {"V": len(d["carriers"]), "E": len(d["edges"]), "carriers_by_kind": dict(sorted(cls.items())),
            "edges_by_kind": dict(sorted(kinds.items()))}


# ------------------------------------------------------------------ obligations
def law_entries(source: str, root: Path = ROOT) -> list[dict]:
    """(rule, subform, facts) of every law of a law set: a DERIVATION.json's laws, or a directory of law files."""
    p = root / source
    if p.name == "DERIVATION.json":
        return [{"rule": x["rule"], "subform": x.get("subform"), "facts": x.get("facts")} for x in load(p)["laws"]]
    out = []
    for f in sorted(p.glob("L*.json")):
        law = load(f)
        out.append({"rule": law["rule"], "subform": law.get("subform"), "facts": law.get("facts")})
    return out


def obligations(source: str, document: str, root: Path = ROOT) -> dict:
    laws = law_entries(source, root)
    mine = [x for x in laws if x["facts"] == document]
    return {"total": len(mine), "law_set_total": len(laws),
            "by_rule": dict(sorted(Counter(x["rule"] for x in mine).items())),
            "by_rule_subform": dict(sorted(Counter(f"{x['rule']}/{x['subform']}" for x in mine).items()))}


# ------------------------------------------------------------------ the catalog pin
def pin_changes(root: Path = ROOT) -> dict:
    pin = load(PIN)["files"]
    tracked = sorted(x for x in git("ls-files", "holon/", cwd=root).split("\n") if x)
    have = {f for f in tracked if (root / f).is_file()}
    return {"modified": sorted(f for f in pin if f in have and sha256(root / f) != pin[f]),
            "deleted": sorted(f for f in pin if f not in have),
            "added": sorted(f for f in have if f not in pin)}


def disclosures(root: Path = ROOT) -> list[dict]:
    p = root / DISCLOSURES.relative_to(ROOT)
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


# ------------------------------------------------------------------ history
def prereg_commit(key: str = "I49") -> str:
    """The first commit, oldest first, whose spec/M4/predictions.json holds the key."""
    for c in git("rev-list", "--topo-order", "--reverse", "HEAD", "--", "spec/M4/predictions.json").split():
        try:
            d = json.loads(git("show", f"{c}:spec/M4/predictions.json"))
        except (subprocess.CalledProcessError, ValueError):
            continue
        if key in d.get("iterations", {}):
            return c
    raise AssertionError(f"no commit holds key {key}")


def first_parent_since(c: str) -> list[str]:
    return git("rev-list", "--first-parent", "--no-merges", "--reverse", f"{c}^..HEAD").split()


def changed(c: str) -> list[str]:
    return [x for x in git("diff-tree", "--no-commit-id", "--name-only", "-r", f"{c}^", c).split("\n") if x]


def added(c: str) -> list[str]:
    return [x for x in git("diff-tree", "--no-commit-id", "--name-only", "--diff-filter=A", "-r", f"{c}^", c).split("\n")
            if x]
