"""I46 instrument (the contract is the docstring of tests_m3/test_blind_rerun.py). Independent of holon/ and of
tools/: it imports nothing from either. It reuses I82's instrument (tests_m3/_i82.py, pinned by I82-R0 and again by
this key's thresholds) for git access, the pack protocol's leak patterns and the alpha-normal form of statements.
Written at the prereg, before the pack commit exists and before any blind run; its sha256 is pinned in the key I46.

It runs holon only where the contract defines a clause by holon's own command: E1 (`holon report --milestone M3
--check`) and the prereg audit, each in a subprocess.

    python -m tests_m3._i46 calls TRANSCRIPT.jsonl     print the tool-call projection of a session transcript
"""
from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path

from tests_m3 import _i82 as I82

ROOT = Path(__file__).resolve().parents[1]
KEY = "I46"
SIDECAR = "spec/M3/lib/blind_rerun.json"
BRIEF = "spec/M3/lib/blind_session.md"
OUT = "audit/blind/I46"
FAMILIES = (("codec", "gen/M3/codec/"), ("goops", "gen/M3/goops/"), ("own", "gen/M3/own/"),
            ("versions", "gen/M3/versions/"), ("bundle", "gen/M3/bundle/"),
            ("rollup", "spec/M2/facts/morph_rollup.extracted.json"))


def sidecar(root=ROOT) -> dict:
    return json.loads((Path(root) / SIDECAR).read_text(encoding="utf-8"))


# ====================================================================== the pack commit
def holds(root, rev: str, path: str) -> bool:
    try:
        I82.git(root, "cat-file", "-e", f"{rev}:{path}")
    except Exception:  # noqa: BLE001
        return False
    return True


def pack_commit(root=ROOT, ref: str | None = None) -> str | None:
    """The oldest commit of ref's first-parent chain whose tree holds the marker (None when none does)."""
    sc = sidecar(root)["pack"]
    ref = ref or sc["lead_ref"]
    found = None
    for c in I82.git(root, "rev-list", "--first-parent", ref, "--", sc["marker"]).split():
        if holds(root, c, sc["marker"]):
            found = c   # rev-list lists newest first, so the last hit is the oldest
    return found


def pack_commit_problems(root, p: str) -> list[str]:
    """What a named pack commit must satisfy without the lead's ref: it holds the marker and its first parent does not."""
    mk = sidecar(root)["pack"]["marker"]
    out = []
    if not holds(root, p, mk):
        out.append(f"{p[:8]} does not hold {mk}")
    if holds(root, f"{p}^1", mk):
        out.append(f"the first parent of {p[:8]} already holds {mk}")
    return out


# ====================================================================== the scope set
def leak_patterns(root, commit: str) -> dict:
    sc = I82.pack_sidecar(root, commit)
    lk = sc["leaks"]
    pats = {c: [re.compile(p) for p in ps] for c, ps in lk["classes"].items()}
    pats["law_name"] = [I82.literal_pattern(n) for n in I82.law_names(root, commit, lk)]
    pats["witness"] = [I82.number_pattern(n) for n in I82.witness_numbers(root, commit, sc)]
    return pats


def _texts(key: str, value) -> list[str]:
    out = [key]
    if isinstance(value, dict):
        return out
    stack = [value]
    while stack:
        v = stack.pop()
        if isinstance(v, dict):
            for k, x in v.items():
                out.append(k)
                stack.append(x)
        elif isinstance(v, list):
            stack.extend(v)
        elif isinstance(v, str):
            out.append(v)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(json.dumps(v))
    return out


def reasons(key: str, value, rules: dict, pats: dict) -> list[str]:
    texts = _texts(key, value)
    why = ["key"] if re.search(rules["strip_key_pattern"], key) else []
    if any(re.search(rules["strip_hash_pattern"], t) for t in texts):
        why.append("hash")
    why += [f"leak:{c}" for c in sorted(pats) if any(p.search(t) for p in pats[c] for t in texts)]
    return why


def strip_doc(doc: dict, rules: dict, pats: dict, at: str = "") -> tuple[dict, dict]:
    kept, gone = {}, {}
    for k, v in doc.items():
        path = f"{at}/{k}" if at else k
        why = reasons(k, v, rules, pats)
        if why:
            gone[path] = why
        elif isinstance(v, dict):
            kept[k], sub = strip_doc(v, rules, pats, path)
            gone.update(sub)
        else:
            kept[k] = v
    return kept, gone


def scope_expected(root, commit: str, rules: dict | None = None) -> dict:
    """{path: {"source": bytes, "kept": doc or None, "stripped": {key path: reasons}}} of the scope set at commit."""
    rules = rules or sidecar(root)["scope"]
    pats = leak_patterns(root, commit)
    out = {}
    for path, _, typ, _ in I82.ls_tree(root, commit):
        if typ != "blob" or not any(fnmatch.fnmatchcase(path, g) for g in rules["files"]):
            continue
        src = I82.show(root, commit, path)
        try:
            doc = json.loads(src.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            doc = None
        if not isinstance(doc, dict):
            out[path] = {"source": src, "kept": None, "stripped": {}}
            continue
        kept, gone = strip_doc(doc, rules, pats)
        out[path] = {"source": src, "kept": kept, "stripped": gone}
    return dict(sorted(out.items()))


def at_base_listing(exp: dict) -> dict:
    return {"given": [p for p, e in exp.items() if e["kept"] is not None],
            "stripped": {p: e["stripped"] for p, e in exp.items() if e["stripped"]},
            "withheld": [p for p, e in exp.items() if e["kept"] is None]}


def scope_problems(root, commit: str, out_dir) -> list[str]:
    """The committed scope set (scope.json, stripped.json, files/) against the protocol's at commit, and the mechanical
    check: no file given still holds a member the strip rules remove."""
    rules = sidecar(root)["scope"]
    exp, d, probs = scope_expected(root, commit, rules), Path(out_dir), []
    pats = leak_patterns(root, commit)
    given = {p: sorted(e["stripped"]) for p, e in exp.items() if e["kept"] is not None}
    try:
        if json.loads((d / "stripped.json").read_text()) != given:
            probs.append("stripped.json differs from the protocol's")
        sj = json.loads((d / "scope.json").read_text())
    except (OSError, ValueError) as e:
        return probs + [f"cannot read the scope set: {e}"]
    if sj.get("commit") != commit:
        probs.append(f"scope.json names commit {str(sj.get('commit'))[:8]}, not {commit[:8]}")
    files = sorted(str(p.relative_to(d / "files")) for p in (d / "files").rglob("*") if p.is_file())
    if files != sorted(given):
        probs.append(f"files/ holds {files}, the protocol gives {sorted(given)}")
    for p, e in exp.items():
        if e["kept"] is None:
            continue
        f = d / "files" / p
        if not f.is_file():
            continue
        if not e["stripped"]:
            if f.read_bytes() != e["source"]:
                probs.append(f"{p}: nothing is stripped, so it must be the source's bytes")
        elif json.loads(f.read_text()) != e["kept"]:
            probs.append(f"{p}: not the protocol's stripped document")
        _, again = strip_doc(json.loads(f.read_text()), rules, pats)
        if again:
            probs.append(f"{p}: still holds members the rules strip: {sorted(again)}")
    return probs


# ====================================================================== the reads check
FILE_TOOLS = {"Read": "file_path", "Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path",
              "NotebookEdit": "notebook_path", "Glob": "path", "Grep": "path"}
BANNED_TOOLS = re.compile(r"^(WebFetch|WebSearch|Agent|Task|mcp__.*)$")
ABS = re.compile(r"(?<![\w.~:$/-])/[^\s'\"`;|&<>(){}\\,]+")
URL = re.compile(r"https?://[^\s'\"`;|&<>()]+")
DOTDOT = re.compile(r"(?:^|[/\s'\"=:])\.\.(?:/|$|[\s'\"])")


def tool_calls(transcript) -> list[dict]:
    """Every tool call of a session transcript (JSON lines; assistant messages' tool_use blocks), in order."""
    calls = []
    for line in Path(transcript).read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        msg = ev.get("message") if isinstance(ev, dict) else None
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list) or (msg.get("role") or ev.get("type")) != "assistant":
            continue
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                calls.append({"i": len(calls), "tool": b.get("name"), "input": b.get("input")})
    return calls


def _strings(v) -> list[str]:
    out, stack = [], [v]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)
        elif isinstance(x, str):
            out.append(x)
    return out


def _under(path: str, roots: list[str]) -> bool:
    return any(path == r.rstrip("/") or path.startswith(r.rstrip("/") + "/") for r in roots)


def calls_problems(calls: list[dict], run: dict, root=ROOT) -> list[str]:
    s = sidecar(root)["session"]
    w, pack, scope = run["W"].rstrip("/"), run["pack"], run["scope"].rstrip("/")
    forbidden = ["/home/user/HOLON", "/root/work/morph"]
    allowed = [w, pack, scope] + list(s["toolchain_prefixes"])
    urls = ["https://github.com/morph-l2/"]
    probs = []
    if not calls:
        probs.append("no tool call: the projection is empty")
    if any(_under(w, [f]) for f in forbidden) or not w.startswith("/"):
        probs.append(f"W {w} is not an absolute path outside every checkout")
    for c in calls:
        tool, inp, at = c.get("tool") or "", c.get("input") or {}, f"call {c.get('i')} ({c.get('tool')})"
        strings = _strings(inp)
        if BANNED_TOOLS.match(tool):
            probs.append(f"{at}: a tool the protocol does not allow")
            continue
        if any(re.search(re.escape(f) + r"(?:[/\s'\"]|$)", v) for f in forbidden for v in strings):
            probs.append(f"{at}: names a checkout of HOLON or of the target outside W")
        if any(DOTDOT.search(v) for v in strings):
            probs.append(f"{at}: a '..' path segment")
        if any("~/" in v or "$HOME" in v for v in strings):
            probs.append(f"{at}: a home-relative path")
        if tool in FILE_TOOLS:
            p = inp.get(FILE_TOOLS[tool])
            if not isinstance(p, str) or not p.startswith("/") or not _under(p, [w]):
                probs.append(f"{at}: its path {p!r} is not under W")
        elif tool == "Bash":
            cmd = inp.get("command") or ""
            if not (cmd.lstrip().startswith(f"cd {w} && ") or cmd.lstrip().startswith(f"mkdir -p {w} && cd {w} && ")):
                probs.append(f"{at}: does not begin with `cd W && `")
            for u in URL.findall(cmd):
                if not any(u.startswith(x) for x in urls):
                    probs.append(f"{at}: a URL outside the target's repositories: {u}")
            for p in ABS.findall(URL.sub(" ", cmd)):
                if not _under(p, allowed):
                    probs.append(f"{at}: the path {p} is outside W and the toolchain")
    return probs


# ====================================================================== the metric, per milestone, rule and family
def _law(tree, m: str, lid: str) -> dict:
    return json.loads((Path(tree) / "laws" / m / f"{lid}.json").read_text(encoding="utf-8"))


def family(facts) -> str:
    for name, prefix in FAMILIES:
        if isinstance(facts, str) and facts.startswith(prefix):
            return name
    return "other"


def breakdown(lead, blind, m: str) -> dict:
    """{"rule": {label: counts}, "family": {label: counts}} over the lead's classes of milestone m."""
    lc, _ = I82.tree_classes(lead, m)
    bc, _ = I82.tree_classes(blind, m)
    out = {"rule": {}, "family": {}}
    for k, c in lc.items():
        laws = [_law(lead, m, lid) for lid in c["laws"]]
        labels = {"rule": "+".join(sorted({x["rule"] for x in laws})),
                  "family": "+".join(sorted({family(x.get("facts")) for x in laws}))}
        for by, label in labels.items():
            g = out[by].setdefault(label, {"lead_classes": 0, "matched": 0, "agree": 0, "disagree": []})
            g["lead_classes"] += 1
            if k in bc:
                g["matched"] += 1
                if bc[k]["status"] == c["status"]:
                    g["agree"] += 1
                else:
                    g["disagree"].append({"lead": c["status"], "blind": bc[k]["status"], "laws": c["laws"]})
    for by in out.values():
        for g in by.values():
            g["matched_fraction"] = g["matched"] / g["lead_classes"] if g["lead_classes"] else None
            g["blind_agreement"] = g["agree"] / g["matched"] if g["matched"] else None
    return out


def flips(cmp: dict) -> list[dict]:
    """Disagreements in which neither side is UNKNOWN (a PROVED/REFUTED flip, or a MIXED class)."""
    return [d for m in cmp["milestones"].values() for d in m["disagreements"]
            if "UNKNOWN" not in (d["lead"]["status"], d["blind"]["status"])]


# ====================================================================== the exit
def exit_clauses(root, p: str, cmp: dict, reads_ok: bool, report_ok: bool) -> dict:
    ex = sidecar(root)["exit"]
    m3 = cmp["milestones"].get("M3") or {"matched": 0, "agree": 0}
    status = json.loads(I82.show(root, p, "results/M3/audit_status.json"))
    back = json.loads(I82.show(root, p, "results/M3/backtest.json"))
    e = {"E1": bool(report_ok),
         "E2": m3["matched"] >= ex["min_matched"] and m3["agree"] >= ex["threshold"] * m3["matched"],
         "E3": status.get("converged") is True,
         "E4": not back.get("exit_blockers"),
         "E5": bool(reads_ok)}
    e["m3_exit"] = all(e[k] for k in ("E1", "E2", "E3", "E4", "E5"))
    e["i46_clause"] = e["E1"] and e["E2"] and e["E5"]
    return e


# ====================================================================== the brief
STATUS_WORDS = re.compile(r"\b(PROVED|REFUTED|UNKNOWN|MIXED)\b")


def brief_problems(root, commit: str) -> list[str]:
    """The brief holds no outcome: no status word, no law id of the tree at commit, no leak-class match."""
    text = (Path(root) / BRIEF).read_text(encoding="utf-8")
    probs = [f"status word {m.group(0)}" for m in STATUS_WORDS.finditer(text)]
    ids = {path.rsplit("/", 1)[1][:-5] for path, _, typ, _ in I82.ls_tree(root, commit)
           if typ == "blob" and re.fullmatch(r"laws/[MT]\d+/L_[^/]+\.json", path)}
    probs += [f"law id {i}" for i in sorted(ids) if re.search(r"(?<![A-Za-z0-9_])" + re.escape(i) + r"(?![A-Za-z0-9_])",
                                                              text)]
    for cls, pats in sorted(leak_patterns(root, commit).items()):
        for pat in pats:
            for mt in pat.finditer(text):
                probs.append(f"leak {cls}: {mt.group(0)!r}")
    return probs


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) == 2 and a[0] == "calls":
        for c in tool_calls(a[1]):
            sys.stdout.write(json.dumps(c, sort_keys=True, ensure_ascii=False) + "\n")
        return 0
    print(__doc__.splitlines()[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
