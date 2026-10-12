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
  check_cross_milestone(derivation, laws, entries, root) -> [problem]

Self-certified until the human freezes this module, keys/ and the registries (Q1): A3
(holon audit regress) and human review are the backstop.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import ir

KINDS = ("reextraction", "binding_change", "strengthening", "weakening", "cross_milestone")
KEY_SUFFIXES = (".asc", ".gpg", ".pub", ".key")
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
    """What a signature covers: the entry without its signature, as canonical JSON."""
    return ir.canonical_json({k: v for k, v in entry.items() if k != "signature"})


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
    imp = implication.prove(old, new, root)
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


def committed_versions(path: Path, root: Path) -> list[bytes]:
    """Every committed version of `path` reachable from HEAD, oldest first (read-only git); [] without git."""
    root = Path(root).resolve()
    try:
        rel = Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return []
    top = _git(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.decode().strip()).resolve() != root:
        return []   # not the top of a checkout (e.g. a copy of the tree): no history to compare with
    p = _git(root, "log", "--topo-order", "--reverse", "--format=%H", "HEAD", "--", rel)
    if p.returncode != 0:
        return []
    out = []
    for c in p.stdout.decode().split():
        b = _git(root, "cat-file", "blob", f"{c}:{rel}")
        if b.returncode == 0:
            out.append(b.stdout)
    return out


def check_file(path: Path, root: Path) -> list[str]:
    """Problems with a STATEMENT_DIFF.jsonl: a line that is not an accepted entry, or a committed version
    that the file does not extend (append-only)."""
    path, root = Path(path), Path(root)
    if not path.is_file():
        return [f"{path} does not exist"]
    data = path.read_bytes()
    problems = []
    for v in committed_versions(path, root):
        if not data.startswith(v):
            problems.append("append-only: the file no longer extends a committed version of itself")
            break
    for n, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError as ex:
            problems.append(f"line {n}: not JSON ({ex})")
            continue
        r = check_entry(e, root)
        if not r["ok"]:
            kind, lid = (e.get("kind"), e.get("law_id") or (e["new"].get("law_id") if _is_law(e.get("new")) else None)) \
                if isinstance(e, dict) else ("?", None)
            problems.append(f"line {n}: {kind} {lid}: {r['reason']}")
    return problems


# ---------------------------------------------------------------- cross-milestone links (A3, L22)
def check_cross_milestone(derivation: dict, laws: dict, entries: list, root: Path) -> list[str]:
    """Every DERIVATION.json back-test link {old, old_milestone, new, new_milestone, basis} needs an accepted
    cross_milestone entry (a checked S_new => S_old) or an accepted signed weakening for exactly that pair,
    carrying the linked statements as they are. A cross_milestone entry for a pair no link names is a
    problem too: pairs come from the derivation, never from ids."""
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
