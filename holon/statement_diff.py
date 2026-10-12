"""laws/STATEMENT_DIFF.jsonl: every statement change goes through an auditable channel (I10; whitepaper
§9.4, §9.5 A3, L14, L22).

The log is append-only: one JSON object per line, {"kind", "law_id", "old": IR, "new": IR, "reason", ...}.
A frozen statement may change only through an entry that this module accepts:

  reextraction     the changed refs come from extractor output that G1 reproduces from the pinned code with
                   the pinned extractor (and `holon derive` reproduces the new statement). A facts file whose
                   extraction.method says it was written by hand never qualifies. No pinned extractor exists
                   yet, so today every reextraction is rejected, with the reason.
  binding_change   an emitted def changed under a fixed statement: a generated, kernel-checked equivalence law
                   between the old and the new def, or a signature. No equivalence generator exists yet, so an
                   unsigned binding_change is rejected.
  strengthening    a kernel-checked S' => S (holon.gen.implication generates the obligation and its proof;
                   Bend, and BendTT when available, must accept it).
  weakening        a gpg signature verifiable against a public key in keys/ (Q3) and an auditor review. A
                   signature is a human act: no key exists, so every weakening is rejected.
  cross_milestone  a later milestone's analogue S_new of an earlier law S_old: a checked S_new => S_old, or a
                   signed weakening. Pairs come from DERIVATION.json back-test links, never from ids
                   (check_cross_milestone).

API:
  check_entry(entry, root) -> {"ok", "reason", "implication"}      implication: holon.gen.implication.prove
  check_file(path, root) -> [problem]                              every line, plus append-only over git history
  scan(path, root) -> {"problems", "entries", "git", "note"}       check_file with each line's verdict
  check_cross_milestone(derivation, laws, entries, root, accepted=None) -> [problem]
  registry_changes(milestone, root) -> {"git", "changes", "note"}  statement-hash changes the log must cover
  tie_problems(milestone, root, scanned) -> ([problem], note)      G2: every change covered by an accepted entry

Each line is checked once, against the tree it was appended to (audit F-M2-22). `python -m holon.statement_diff
append ENTRY.json` runs check_entry on the working tree and, only when it accepts, appends the entry with an
`accepted` record: the sha256 of every facts file the entry's statements are about and, for an implication, the
sha256 of the generated obligation and of the proof Bend accepted. Then:
  * a line not yet committed (beyond HEAD's version of the log) is checked in full against the working tree, and
    its recorded hashes must equal the ones the check gives now;
  * a committed line is not re-proved: its recorded facts hashes must equal those files at the commit that
    appended it (read-only git cat-file). A later facts change therefore never invalidates an accepted line, and
    the append-only log never keeps G2 red because of one.
Off git (a copied tree) every line counts as new and is checked against the working tree.

The statement-change tie (audit F-M2-08, whitepaper G2 "changes only per §9.4"): every law whose registry hash
changed, in a commit after the log was introduced or in the working tree against HEAD, or which was deleted, needs
an accepted entry for that law whose old and new statements are exactly the two versions (a deletion: an accepted
weakening whose old is the deleted statement). Off git the tie cannot run, and G2 says so instead of passing it
silently.

Self-certified until the human freezes this module, keys/ and the registries (Q1): A3
(holon audit regress) and human review are the backstop.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import ir

KINDS = ("reextraction", "binding_change", "strengthening", "weakening", "cross_milestone")
KEY_SUFFIXES = (".asc", ".gpg", ".pub", ".key")
LOG = Path("laws") / "STATEMENT_DIFF.jsonl"
STATEMENT_KINDS = ("reextraction", "binding_change", "strengthening", "weakening")   # kinds that change one law
# what identifies a statement (the hashed keys of every IR version, and the facts file it is about)
_CORE = tuple(dict.fromkeys(ir.HASHED_KEYS + ir.HASHED_KEYS_03 + ("facts",)))


def _res(ok: bool, reason: str, implication: dict | None = None) -> dict:
    return {"ok": ok, "reason": reason, "implication": implication}


def _is_law(x) -> bool:
    return isinstance(x, dict) and isinstance(x.get("law_id"), str) and isinstance(x.get("statement"), dict)


def core(law: dict) -> bytes:
    return ir.canonical_json({k: law.get(k) for k in _CORE})


# ---------------------------------------------------------------- signatures (Q3)
def signed_payload(entry: dict) -> bytes:
    """What a signature covers: the entry without its signature and without the acceptance record the append tool
    adds after checking it, as canonical JSON."""
    return ir.canonical_json({k: v for k, v in entry.items() if k not in ("signature", "accepted")})


def verify_signature(entry: dict, root: Path) -> tuple[bool, str]:
    """A detached, ASCII-armored gpg signature over signed_payload(entry), made by a key in keys/. The keys
    are imported into a throwaway GNUPGHOME, so no keyring outside keys/ is trusted."""
    sig = entry.get("signature")
    if not isinstance(sig, str) or not sig.strip():
        return False, "no gpg signature: this needs a signature verifiable against keys/ (Q3)"
    kdir = Path(root) / "keys"
    keys = sorted(p for p in kdir.glob("*") if p.is_file() and p.suffix in KEY_SUFFIXES) if kdir.is_dir() else []
    if not keys:
        return False, "the signature cannot be verified: keys/ holds no public key (a signature is a human act, Q3)"
    gpg = shutil.which("gpg")
    if not gpg:
        return False, "the signature cannot be verified: gpg is not installed"
    home = Path(tempfile.mkdtemp(prefix="holon-gpg-"))
    try:
        os.chmod(home, 0o700)
        env = {"GNUPGHOME": str(home), "PATH": os.environ.get("PATH", ""), "LC_ALL": "C"}
        imp = subprocess.run([gpg, "--batch", "--quiet", "--import", *map(str, keys)], env=env, capture_output=True)
        if imp.returncode != 0:
            return False, "the signature cannot be verified: the keys in keys/ do not import"
        (home / "payload").write_bytes(signed_payload(entry))
        (home / "payload.asc").write_text(sig)
        v = subprocess.run([gpg, "--batch", "--status-fd", "1", "--verify", str(home / "payload.asc"), str(home / "payload")],
                           env=env, capture_output=True, text=True)
        if v.returncode == 0 and "[GNUPG:] VALIDSIG" in v.stdout:
            return True, "gpg signature verified against keys/"
        return False, "the gpg signature does not verify against keys/"
    finally:
        shutil.rmtree(home, ignore_errors=True)


# ---------------------------------------------------------------- entries
def check_entry(entry: dict, root: Path) -> dict:
    root = Path(root)
    if not isinstance(entry, dict):
        return _res(False, "an entry is a JSON object")
    kind = entry.get("kind")
    if kind not in KINDS:
        return _res(False, f"unknown entry kind {kind!r} (one of {', '.join(KINDS)})")
    old, new = entry.get("old"), entry.get("new")
    if not (_is_law(old) and _is_law(new)):
        return _res(False, "an entry carries the old and the new statement as law IR")
    if kind in ("reextraction", "binding_change", "strengthening"):
        lid = entry.get("law_id", old["law_id"])
        if not old["law_id"] == new["law_id"] == lid:
            return _res(False, f"a {kind} changes one law: old, new and law_id must name the same law")
    if kind == "weakening":
        ok, why = verify_signature(entry, root)
        if not ok:
            return _res(False, f"unsigned or unverified weakening: {why}")
        if not entry.get("review"):
            return _res(False, "a signed weakening also needs an auditor review (\"review\")")
        return _res(True, f"weakening: {why}; reviewed")
    if kind == "reextraction":
        return _reextraction(entry, old, new, root)
    if kind == "binding_change":
        if core(old) != core(new):
            return _res(False, "a binding_change keeps the statement fixed, and this entry changes it")
        ok, why = verify_signature(entry, root)
        if ok:
            return _res(True, f"binding_change: {why}")
        return _res(False, "a binding_change needs a generated, kernel-checked equivalence law between the old and "
                           "the new def (no equivalence generator exists yet; a supplied proof does not count) or a "
                           f"signature: {why}")
    if kind == "cross_milestone" and old.get("milestone") == new.get("milestone"):
        return _res(False, "a cross_milestone entry links laws of two milestones (a change within one is a strengthening)")
    # strengthening, cross_milestone: a checked new => old
    from .gen import implication
    bm = entry.get("binder_map")
    imp = implication.prove(old, new, root, binder_map=bm if isinstance(bm, dict) else None)
    if imp["status"] == "PROVED":
        return _res(True, f"{kind}: {imp['reason']}", imp)
    return _res(False, f"{kind} without a checked {new['law_id']} => {old['law_id']} ({imp['status']}: {imp['reason']})", imp)


def _reextraction(entry: dict, old: dict, new: dict, root: Path) -> dict:
    rel = entry.get("facts") or new.get("facts")
    if not isinstance(rel, str) or not (root / rel).is_file():
        return _res(False, f"a reextraction names the facts file it comes from (got {rel!r})")
    try:
        facts = json.loads((root / rel).read_text())
    except ValueError as e:
        return _res(False, f"{rel} is not JSON: {e}")
    ext = facts.get("extraction") if isinstance(facts, dict) else None
    method = str(ext.get("method", "")) if isinstance(ext, dict) else ""
    if not method or "hand" in method.lower():
        return _res(False, f"{rel} is hand-written (extraction.method = {method!r}): a reextraction must come from "
                           "extractor output that G1 reproduces from the pinned code with the pinned extractor")
    return _res(False, f"no pinned extractor reproduces {rel} (extraction.method = {method!r}): G1 cannot re-run an "
                       "extraction and `holon derive` does not exist yet, so no reextraction is accepted")


# ---------------------------------------------------------------- the log
def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1", LC_ALL="C")
    return subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=off", *args], capture_output=True, env=env,
                          stdin=subprocess.DEVNULL)


def in_git(root: Path) -> bool:
    """Is root the top of a git checkout with a HEAD (read-only)? A copied tree is not."""
    root = Path(root).resolve()
    top = _git(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.decode().strip()).resolve() != root:
        return False
    return _git(root, "rev-parse", "--verify", "HEAD^{commit}").returncode == 0


def blob_at(root: Path, commit: str, rel: str) -> bytes | None:
    b = _git(Path(root).resolve(), "cat-file", "blob", f"{commit}:{rel}")
    return b.stdout if b.returncode == 0 else None


def committed_history(path: Path, root: Path) -> list[tuple[str, bytes]] | None:
    """[(commit, bytes)] of every committed version of `path` reachable from HEAD, oldest first (read-only git);
    None without git history (e.g. a copy of the tree)."""
    root = Path(root).resolve()
    try:
        rel = Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return None
    if not in_git(root):
        return None
    p = _git(root, "log", "--topo-order", "--reverse", "--format=%H", "HEAD", "--", rel)
    if p.returncode != 0:
        return None
    out = []
    for c in p.stdout.decode().split():
        b = blob_at(root, c, rel)
        if b is not None:
            out.append((c, b))
    return out


def committed_versions(path: Path, root: Path) -> list[bytes]:
    """Every committed version of `path` reachable from HEAD, oldest first (read-only git); [] without git."""
    return [b for _, b in committed_history(path, root) or []]


def _sha(text) -> str | None:
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8") if isinstance(text, str) else text).hexdigest()


def acceptance(entry: dict, result: dict, root: Path) -> dict:
    """The record of what an accepted entry was checked against: every facts file its statements are about
    (sha256), and for an implication the generated obligation and the proof Bend accepted (sha256)."""
    root = Path(root)
    facts = {}
    for side in ("old", "new"):
        rel = entry.get(side, {}).get("facts") if _is_law(entry.get(side)) else None
        if isinstance(rel, str) and (root / rel).is_file():
            facts[rel] = _sha((root / rel).read_bytes())
    acc = {"kind": entry.get("kind"), "facts": dict(sorted(facts.items()))}
    imp = result.get("implication") or {}
    if imp.get("status") == "PROVED":
        acc["implication"] = {"law_id": imp.get("law_id"), "generator": imp.get("generator"),
                              "kernels": imp.get("kernels"), "laws_sha256": _sha(imp.get("laws")),
                              "proof_sha256": _sha(imp.get("proof"))}
    if entry.get("signature"):
        acc["signature"] = "verified against keys/"
    return acc


def _line_tag(e) -> str:
    if not isinstance(e, dict):
        return "? None"
    lid = e.get("law_id") or (e["new"].get("law_id") if _is_law(e.get("new")) else None)
    return f"{e.get('kind')} {lid}"


def scan(path: Path, root: Path) -> dict:
    """Every line of a STATEMENT_DIFF.jsonl with its verdict (see the module docstring):
    {"problems": [..], "entries": [{"line", "entry", "ok", "committed", "commit"}], "git": bool, "note": str}."""
    path, root = Path(path), Path(root)
    out = {"problems": [], "entries": [], "git": False, "note": ""}
    if not path.is_file():
        out["problems"].append(f"{path} does not exist")
        return out
    data = path.read_bytes()
    hist = committed_history(path, root)
    out["git"] = hist is not None
    spans, prev = [], 0   # (end offset, commit): the bytes up to `end` were appended by `commit`
    for c, v in hist or []:
        if not data.startswith(v):
            out["problems"].append("append-only: the file no longer extends a committed version of itself")
            spans = []
            break
        if len(v) > prev:
            spans.append((len(v), c))
            prev = len(v)
    committed_len = spans[-1][0] if spans else 0
    out["note"] = ("no git history (a copied tree): every line checked against the working tree" if hist is None else
                   f"{sum(1 for _, c in spans)} committed versions; committed lines verified against the commit that "
                   "appended them, new lines checked against the working tree")
    offset = 0
    for n, raw in enumerate(data.splitlines(keepends=True), start=1):
        start, offset = offset, offset + len(raw)
        line = raw.decode("utf-8", errors="replace")
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError as ex:
            out["problems"].append(f"line {n}: not JSON ({ex})")
            continue
        commit = next((c for end, c in spans if start < end), None) if start < committed_len else None
        item = {"line": n, "entry": e, "ok": False, "committed": commit is not None, "commit": commit}
        out["entries"].append(item)
        acc = e.get("accepted") if isinstance(e, dict) else None
        if commit is not None:
            why = _verify_committed(e, acc, commit, root)
            if why:
                out["problems"].append(f"line {n}: {_line_tag(e)}: {why}")
            else:
                item["ok"] = True
            continue
        r = check_entry(e, root)
        if not r["ok"]:
            out["problems"].append(f"line {n}: {_line_tag(e)}: {r['reason']}")
        elif not isinstance(acc, dict):
            out["problems"].append(f"line {n}: {_line_tag(e)}: accepted, but the line carries no acceptance record "
                                   "(append entries with `python -m holon.statement_diff append ENTRY.json`)")
        elif ir.canonical_json(acc) != ir.canonical_json(acceptance(e, r, root)):
            out["problems"].append(f"line {n}: {_line_tag(e)}: its acceptance record differs from the check of the "
                                   "working tree")
        else:
            item["ok"] = True
    return out


def _verify_committed(e, acc, commit: str, root: Path) -> str | None:
    """A committed line is not re-proved: its acceptance record must name the facts as they were at the commit
    that appended it."""
    if not isinstance(e, dict) or not isinstance(acc, dict) or not isinstance(acc.get("facts"), dict):
        return f"committed at {commit[:7]} without an acceptance record (only `holon.statement_diff append` writes one)"
    if acc.get("kind") != e.get("kind"):
        return f"its acceptance record is for kind {acc.get('kind')!r}"
    if e.get("kind") in ("strengthening", "cross_milestone") and not isinstance(acc.get("implication"), dict):
        return "its acceptance record names no checked implication"
    if e.get("kind") in ("weakening", "binding_change") and acc.get("signature") != "verified against keys/":
        return "its acceptance record names no verified signature"
    if e.get("kind") == "reextraction":
        return "no reextraction is accepted (no pinned extractor)"
    for rel, sha in sorted(acc["facts"].items()):
        b = blob_at(root, commit, rel)
        if b is None or _sha(b) != sha:
            return (f"its acceptance names {rel} at sha256 {str(sha)[:12]}.., but at {commit[:7]} that file "
                    f"{'does not exist' if b is None else 'hashes to ' + _sha(b)[:12] + '..'}")
    return None


def check_file(path: Path, root: Path) -> list[str]:
    """Problems with a STATEMENT_DIFF.jsonl: a line that is not an accepted entry, or a committed version
    that the file does not extend (append-only)."""
    return scan(path, root)["problems"]


def append(entry: dict, root: Path) -> dict:
    """Check an entry against the working tree and, when accepted, append it with its acceptance record to
    laws/STATEMENT_DIFF.jsonl. Returns check_entry's result."""
    root = Path(root)
    r = check_entry(entry, root)
    if r["ok"]:
        line = json.dumps({**entry, "accepted": acceptance(entry, r, root)}, sort_keys=True, ensure_ascii=False)
        p = root / LOG
        data = p.read_bytes() if p.exists() else b""
        if data and not data.endswith(b"\n"):
            data += b"\n"
        p.write_bytes(data + line.encode("utf-8") + b"\n")
    return r


# ---------------------------------------------------------------- the statement-change tie (G2, F-M2-08)
def cutoff_commit(root: Path) -> str | None:
    """The first commit (in HEAD's history) that added the log: statement changes after it need an entry."""
    p = _git(Path(root).resolve(), "log", "--topo-order", "--reverse", "--diff-filter=A", "--format=%H", "HEAD",
             "--", LOG.as_posix())
    cs = p.stdout.decode().split() if p.returncode == 0 else []
    return cs[0] if cs else None


def _json_or_none(b: bytes | None):
    try:
        return json.loads(b) if b is not None else None
    except ValueError:
        return None


def registry_changes(milestone: str, root: Path) -> dict:
    """Statement-hash changes of laws/<m>/REGISTRY.json the log must cover: in every commit after the log was
    introduced (against its first parent) and in the working tree against HEAD. Each change: {"law_id", "old",
    "new" (law IR or None for a deletion), "at"}. {"git": False} without history."""
    root = Path(root).resolve()
    reg_rel = f"laws/{milestone}/REGISTRY.json"
    if not in_git(root):
        return {"git": False, "changes": [], "note": "not run: no git history (a copied tree), so the registry cannot "
                                                     "be compared with its committed versions"}
    cut = cutoff_commit(root)
    pairs = []   # (at, parent registry, child registry, old laws dir rev, new laws dir rev | None for the tree)
    if cut is not None:
        p = _git(root, "log", "--topo-order", "--reverse", "--format=%H", "HEAD", "--", reg_rel)
        for c in (p.stdout.decode().split() if p.returncode == 0 else []):
            if _git(root, "merge-base", "--is-ancestor", cut, c).returncode != 0:
                continue
            parent = _git(root, "rev-parse", "--verify", "-q", f"{c}^1")
            if parent.returncode != 0:
                continue
            pc = parent.stdout.decode().strip()
            pairs.append((c[:7], _json_or_none(blob_at(root, pc, reg_rel)), _json_or_none(blob_at(root, c, reg_rel)),
                          pc, c))
    cur = root / reg_rel
    head = _json_or_none(blob_at(root, "HEAD", reg_rel))
    if cur.is_file():
        pairs.append(("working tree", head, _json_or_none(cur.read_bytes()), "HEAD", None))
    changes, seen = [], set()
    for at, a, b, ra, rb in pairs:
        sa = (a or {}).get("statements") if isinstance(a, dict) else None
        sb = (b or {}).get("statements") if isinstance(b, dict) else None
        if not isinstance(sa, dict):
            continue   # no earlier registry: every law is an addition
        sb = sb if isinstance(sb, dict) else {}
        for lid in sorted(sa):
            if lid in sb and sb[lid] == sa[lid]:
                continue
            old = _json_or_none(blob_at(root, ra, f"laws/{milestone}/{lid}.json"))
            if lid in sb:
                f = root / "laws" / milestone / f"{lid}.json"
                new = _json_or_none(f.read_bytes() if rb is None and f.is_file() else
                                    blob_at(root, rb, f"laws/{milestone}/{lid}.json") if rb else None)
            else:
                new = None
            key = (lid, core(old) if _is_law(old) else None, core(new) if _is_law(new) else None)
            if key in seen:
                continue
            seen.add(key)
            changes.append({"law_id": lid, "old": old, "new": new, "at": at,
                            "old_hash": sa[lid], "new_hash": sb.get(lid)})
    return {"git": True, "changes": changes,
            "note": f"{len(changes)} statement-hash changes since the log was introduced"
                    + (f" ({cut[:7]})" if cut else " (log not committed yet: working tree against HEAD only)")}


def covers(e: dict, ch: dict) -> bool:
    """Does an entry carry exactly the two statements of a registry change?"""
    if not isinstance(e, dict) or e.get("kind") not in STATEMENT_KINDS or not _is_law(e.get("old")):
        return False
    if (e.get("law_id") or e["old"].get("law_id")) != ch["law_id"] or not _is_law(ch.get("old")):
        return False
    if core(e["old"]) != core(ch["old"]):
        return False
    if ch.get("new") is None:   # a deletion drops a claim: only a signed weakening covers it
        return e.get("kind") == "weakening"
    return _is_law(e.get("new")) and _is_law(ch["new"]) and core(e["new"]) == core(ch["new"])


def tie_problems(milestone: str, root: Path, scanned: dict) -> tuple[list[str], str]:
    """G2: every registry change of the milestone is covered by an accepted entry. Returns (problems, note)."""
    rc = registry_changes(milestone, root)
    if not rc["git"]:
        return [], rc["note"]
    ok = [x["entry"] for x in scanned.get("entries", []) if x.get("ok")]
    bad = []
    for ch in rc["changes"]:
        if not any(covers(e, ch) for e in ok):
            what = "deleted" if ch.get("new") is None else f"hash {str(ch['old_hash'])[:19]}.. -> {str(ch['new_hash'])[:19]}.."
            bad.append(f"{ch['law_id']} {what} ({ch['at']}) without an accepted laws/STATEMENT_DIFF.jsonl entry "
                       "carrying exactly those statements")
    return bad, rc["note"]


# ---------------------------------------------------------------- cross-milestone links (A3, L22)
def check_cross_milestone(derivation: dict, laws: dict, entries: list, root: Path, accepted=None) -> list[str]:
    """Every DERIVATION.json back-test link {old, old_milestone, new, new_milestone, basis} needs an accepted
    cross_milestone entry (a checked S_new => S_old) or an accepted signed weakening for exactly that pair,
    carrying the linked statements as they are. A cross_milestone entry for a pair no link names is a
    problem too: pairs come from the derivation, never from ids. A link may carry a binder_map {new binder: old
    binder} (audit F-M2-23); an entry without its own map is checked with the link's. accepted: a predicate over
    entries (G2 passes scan()'s verdicts, so a committed entry is not re-proved); default check_entry."""
    links = derivation.get("links") if isinstance(derivation, dict) else None
    if not isinstance(links, list):
        return ["the derivation has no list of links"]
    problems, pairs = [], set()
    for i, ln in enumerate(links):
        if not isinstance(ln, dict) or not all(isinstance(ln.get(k), str) and ln[k]
                                               for k in ("old", "old_milestone", "new", "new_milestone", "basis")):
            problems.append(f"link {i}: needs old, old_milestone, new, new_milestone and basis")
            continue
        old, new = ln["old"], ln["new"]
        tag = f"link {new} ({ln['new_milestone']}) -> {old} ({ln['old_milestone']})"
        pairs.add((old, new))
        if ln["old_milestone"] == ln["new_milestone"]:
            problems.append(f"{tag}: both laws are in one milestone")
            continue
        lo, lnw = laws.get(old), laws.get(new)
        if not (_is_law(lo) and _is_law(lnw)):
            problems.append(f"{tag}: the linked laws are not both given")
            continue
        if lo.get("milestone", ln["old_milestone"]) != ln["old_milestone"] or \
                lnw.get("milestone", ln["new_milestone"]) != ln["new_milestone"]:
            problems.append(f"{tag}: the laws' milestones differ from the link's")
            continue
        cands = [e for e in entries if isinstance(e, dict) and e.get("kind") in ("cross_milestone", "weakening")
                 and _is_law(e.get("old")) and _is_law(e.get("new"))
                 and e["old"]["law_id"] == old and e["new"]["law_id"] == new]
        if not cands:
            problems.append(f"{tag}: no cross_milestone entry with a checked {new} => {old}, and no signed weakening")
            continue
        why = []
        for e in cands:
            if core(e["old"]) != core(lo) or core(e["new"]) != core(lnw):
                why.append(f"{e['kind']} entry does not carry the linked statements as they are")
                continue
            if isinstance(ln.get("binder_map"), dict) and "binder_map" not in e:
                e = {**e, "binder_map": ln["binder_map"]}
            if accepted is not None:
                if accepted(e):
                    break
                why.append(f"{e['kind']}: not an accepted entry of laws/STATEMENT_DIFF.jsonl")
                continue
            r = check_entry(e, root)
            if r["ok"]:
                break
            why.append(f"{e['kind']}: {r['reason']}")
        else:
            problems.append(f"{tag}: " + "; ".join(why))
    for e in entries:
        if isinstance(e, dict) and e.get("kind") == "cross_milestone" and _is_law(e.get("old")) and _is_law(e.get("new")) \
                and (e["old"]["law_id"], e["new"]["law_id"]) not in pairs:
            problems.append(f"cross_milestone entry pairs {e['new']['law_id']} with {e['old']['law_id']}, but no "
                            "DERIVATION.json link does (pairs come from back-test links, never from ids)")
    return problems


# ---------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    """python -m holon.statement_diff append ENTRY.json [--root DIR]: check the entry against the working tree and
    append it, with its acceptance record, only if accepted. python -m holon.statement_diff check [--root DIR]:
    print the verdict of every line."""
    import argparse
    ap = argparse.ArgumentParser(prog="python -m holon.statement_diff")
    ap.add_argument("command", choices=("append", "check"))
    ap.add_argument("entry", nargs="?")
    ap.add_argument("--root", default=str(ir.ROOT))
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    if a.command == "append":
        if not a.entry:
            ap.error("append needs ENTRY.json")
        r = append(json.loads(Path(a.entry).read_text()), root)
        print(("appended: " if r["ok"] else "rejected, not appended: ") + r["reason"])
        return 0 if r["ok"] else 1
    s = scan(root / LOG, root)
    print(s["note"])
    for x in s["entries"]:
        print(f"line {x['line']}: {_line_tag(x['entry'])}: {'accepted' if x['ok'] else 'NOT accepted'}"
              + (f" (committed at {x['commit'][:7]})" if x["committed"] else " (new)"))
    for p in s["problems"]:
        print("PROBLEM", p)
    return 0 if not s["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
