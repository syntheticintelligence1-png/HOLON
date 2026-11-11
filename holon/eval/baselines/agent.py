"""agent_review (one fresh reviewer per system) and the blinded match adjudicator (I52_baselines.json).

Reviewer. Morph: the scope files at the pinned commit, copied into a fresh /tmp directory. Corpus: I48's isomorphic
renamings only: each entry's labelled files renamed by holon.eval.rename (seed I52:<entry>) under <entry>/. One
`claude -p` process per system (the protocol's invocation; tools Read, Grep and Glob), the frozen prompt with the
packet's sorted listing and the reviewer's minutes, killed at the budget. Its findings are mapped back: <entry>/<path>
names the entry and the pre-fix file, and a renamed file's lines go back through the map's removed comments.

Adjudicator. One fresh tool-less process per located group (baseline, target, label), the frozen template
spec/M4/lib/I52_match_prompt.md filled with the label's text and the group's findings; it never sees the baseline's
name. The model of a tag is observed at run time and kept outside the repository (~/.holon/eval/baselines/models.json).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .. import common, rename
from . import core

MODELS = core.HOME / "models.json"
WP = core.ROOT / "whitepaper.md"


def _argv(template: list[str], system_prompt: str, model: str) -> list[str]:
    return [system_prompt if a == "<system_prompt>" else model if a == "<model>" else a for a in template]


def _env(removed: list[str]) -> dict:
    e = {k: v for k, v in os.environ.items() if k not in removed}
    return e


def _check_model(tag: str, cli: dict) -> None:
    used = sorted((cli.get("modelUsage") or {}).keys())
    store = core.load(MODELS) if MODELS.is_file() else {}
    if len(used) != 1:
        raise common.Refused(f"a call reported {len(used)} models")
    if store.get(tag) not in (None, used[0]):
        raise common.Refused(f"tag {tag} was observed with another model")
    store[tag] = used[0]
    MODELS.parent.mkdir(parents=True, exist_ok=True)
    MODELS.write_text(json.dumps(store, indent=1, sort_keys=True))


def review_prompt(files: list[str], minutes: int) -> str:
    t = core.REVIEW_PROMPT.read_text(encoding="utf-8")
    return t.replace("{{MINUTES}}", str(minutes)).replace("{{FILES}}", "\n".join(f"- {f}" for f in files))


def _line_map(original: bytes, comments: list[dict]):
    """renamed line -> pre-fix line, from the map's removed comments of one file (identifier renames keep lines)."""
    starts = [0] + [i + 1 for i, ch in enumerate(original) if ch == 10]

    def line_of(off):
        lo, hi = 0, len(starts)
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if starts[mid] <= off:
                lo = mid
            else:
                hi = mid
        return lo + 1
    marks, cum = [], 0
    for c in sorted(comments, key=lambda c: c["offset"]):
        k = c["text"].count("\n") - c["replaced_by"].count("\n")
        if k:
            end_line_orig = line_of(c["offset"]) + c["text"].count("\n")
            cum += k
            marks.append((end_line_orig - cum, cum))  # renamed lines after this one shift by cum

    def back(r: int) -> int:
        d = 0
        for at, cm in marks:
            if r > at:
                d = cm
        return r + d
    return back


def packet(system: str, wall_s: int) -> dict:
    """Build the review packet: {"dir", "files" (sorted listing), "per_target" {t: [files]}, "back" {listing path:
    (target, pre-fix path, map info)}}."""
    d = Path(tempfile.mkdtemp(prefix="review-", dir="/tmp"))
    per, back = {}, {}
    if core.pinned(system) or system == core.HELDOUT:  # I52b: the held-out packet is its scope files, as Morph's
        tgt = core.targets(system)[0]
        src = core.checkout(system, tgt)
        files = core.scope_files(src, system, tgt)
        for f in files:
            (d / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / f, d / f)
            back[f] = (tgt, f, None)
        per[tgt] = files
    else:
        for eid in core.targets(system):
            e = core.entry(eid)
            src = core.checkout(system, eid)
            mp = core.WORK / system / eid / "rename-map.json"
            m, _ = rename.rename(src, list(e["files"]), f"I52:{eid}", d / eid, mp, verify=True)
            per[eid] = []
            for f in e["files"]:
                p = f"{eid}/{f}"
                per[eid].append(p)
                cs = [c for c in m["comments"] if c["path"] == f]
                back[p] = (eid, f, _line_map((src / f).read_bytes(), cs))
    listing = sorted(p for fs in per.values() for p in fs)
    return {"dir": d, "files": listing, "per_target": per, "back": back}


def run_reviewer(system: str, model: str) -> dict:
    proto = core.protocol()["baselines"]["agent_review"]
    wall = core.budget(system)["wall_s"] * len(core.targets(system))
    pk = packet(system, wall)
    prompt = review_prompt(pk["files"], wall // 60)
    argv = _argv(proto["invocation"], proto["system_prompt"], model)
    t0 = time.monotonic()
    try:
        p = subprocess.run(argv, input=prompt, capture_output=True, text=True, cwd=str(pk["dir"]), timeout=wall,
                           env=_env(proto["env_removed"]))
        out, timed_out = p.stdout, False
    except subprocess.TimeoutExpired as ex:
        out, timed_out = (ex.stdout or b"").decode() if isinstance(ex.stdout, bytes) else (ex.stdout or ""), True
    dt = time.monotonic() - t0
    shutil.rmtree(pk["dir"], ignore_errors=True)
    try:
        cli = json.loads(out)
    except json.JSONDecodeError:
        cli = {}
    if cli:
        _check_model("A", cli)
    result = cli.get("result") or ""
    parsed, findings = None, {t: [] for t in pk["per_target"]}
    m = re.search(r"\{.*\}", result, re.S)
    if m:
        try:
            parsed = json.loads(m.group(0))
        except json.JSONDecodeError:
            parsed = None
    for f in (parsed or {}).get("findings", []) if isinstance(parsed, dict) else []:
        path = str(f.get("file", "")).lstrip("./")
        if path not in pk["back"]:
            continue
        t, orig, back = pk["back"][path]
        try:
            a, b = (int(x) for x in (f.get("lines") or [0, 0])[:2])
        except (TypeError, ValueError):
            continue
        if back:
            a, b = back(a), back(b)
        findings[t].append(core.finding(str(f.get("kind") or "review"), str(f.get("message") or ""),
                                        [core.loc(orig, min(a, b), max(a, b))]))
    usage = cli.get("usage") or {}
    rec = {"system": system, "prompt_sha256": core.sha256_text(prompt), "packet": pk["files"],
           "per_target": pk["per_target"], "timed_out": timed_out, "parsed": parsed is not None,
           "cli": {k: cli.get(k) for k in ("is_error", "num_turns", "subtype", "session_id")},
           "findings": findings, "wall_s": round(dt, 3), "budget_s": wall,
           "tokens": {k: usage.get(k) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                "cache_creation_input_tokens")},
           "result_text": result[-20000:]}
    p = reviewer_path(system)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, indent=1, sort_keys=True))
    return rec


def reviewer_path(system: str) -> Path:
    return core.HOME / "agent" / f"{core.tiered(system)}.json"


# ------------------------------------------------------------------------------------------------- adjudicator
def _whitepaper_rows():
    text = WP.read_text(encoding="utf-8")
    obs, prior, new = {}, {}, {}
    for line in text.splitlines():
        m = re.match(r"^\| (O\d+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", line)
        if m:
            obs[m.group(1)] = [x.strip() for x in m.groups()[1:]]
        m = re.match(r"^\| (F\d+) \| (.+) \|$", line)
        if m:
            prior[m.group(1)] = m.group(2).strip()
    for m in re.finditer(r"^\*\*(N\d) \((O\d+)\)\.\*\* (.+)$", text, re.M):
        new[m.group(1)] = m.group(3).strip()
    return obs, prior, new


def defect_text(system: str, label: str) -> str:
    if system == "corpus":
        e = core.entry(label)
        return f"Title: {e['title']}\nDescription: {e['description']}"
    obs, prior, new = _whitepaper_rows()
    rule, title, impact, pr = obs[label]
    ids = re.findall(r"[FN]\d+", pr)
    extra = "".join(f"\nRelated prior finding {i}: {prior.get(i) or new.get(i) or ''}" for i in ids)
    return f"Rule: {rule}\nObstruction: {title}\nImpact (sink / reach / persistence): {impact}{extra}"


def match_prompt(system: str, label: str, findings: list[dict]) -> str:
    if system == core.HELDOUT:
        return heldout_match_prompt(core.heldout_labels()[label]["action"], findings)
    t = core.MATCH_PROMPT.read_text(encoding="utf-8")
    rows = "\n".join(json.dumps({k: f[k] for k in ("id", "kind", "message", "locations")}, sort_keys=True,
                                ensure_ascii=False) for f in findings)
    return t.replace("{{DEFECT}}", defect_text(system, label)).replace("{{FINDINGS}}", rows)


def adjudicate(system: str, label: str, findings: list[dict], model: str) -> dict:
    proto = core.protocol()["matching"]["adjudicator"]
    prompt = match_prompt(system, label, findings)
    argv = _argv(proto["invocation"], proto["system_prompt"], model)
    ids = {f["id"] for f in findings}
    attempts, confirmed = [], None
    for _ in range(2):
        d = Path(tempfile.mkdtemp(prefix="match-", dir="/tmp"))
        try:
            p = subprocess.run(argv, input=prompt, capture_output=True, text=True, cwd=str(d), timeout=600,
                               env=_env(["CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD", "CLAUDE_ADDITIONAL_DIRECTORIES"]))
            out = p.stdout
        except subprocess.TimeoutExpired:
            out = ""
        shutil.rmtree(d, ignore_errors=True)
        try:
            cli = json.loads(out)
        except json.JSONDecodeError:
            cli = {}
        if cli:
            _check_model("A", cli)
        res = cli.get("result") or ""
        ans = None
        m = re.search(r"\{.*\}", res, re.S)
        if m:
            try:
                ans = json.loads(m.group(0))
            except json.JSONDecodeError:
                ans = None
        ok = isinstance(ans, dict) and isinstance(ans.get("describes"), list) and all(isinstance(x, str) for x in ans["describes"])
        attempts.append({"is_error": cli.get("is_error"), "num_turns": cli.get("num_turns"), "result": res[-4000:],
                         "outcome": "ok" if ok else "unparsable"})
        if ok:
            confirmed = sorted(set(ans["describes"]) & ids)
            break
    return {"label": label, "findings": sorted(ids), "confirmed": confirmed or [],
            "prompt_sha256": core.sha256_text(prompt), "attempts": attempts}


# ------------------------------------------------------------------------------------------------- I52b: obligation labels
RULES = ("DISCH", "FACT", "SORT", "SYM", "UNDO")


def heldout_match_prompt(action: str, findings: list[dict]) -> str:
    """The held-out adjudicator's prompt for one (baseline, action) group (I52b_heldout.json matching.adjudicator): the
    frozen template filled with the action, the five rules' obligations and the located findings."""
    h = core.heldout()
    t = (core.ROOT / "spec" / "M4" / "lib" / "I52b_match_prompt.md").read_text(encoding="utf-8")
    obl = h["labels"]["obligations"]
    rows = "\n".join(json.dumps({k: f[k] for k in ("id", "kind", "message", "locations")}, sort_keys=True,
                                ensure_ascii=False) for f in findings)
    return (t.replace("{{ACTION}}", action)
            .replace("{{OBLIGATIONS}}", "\n".join(f"- {r}: {obl[r]}" for r in RULES))
            .replace("{{FINDINGS}}", rows))


def adjudicate_heldout(action: str, labels: dict, findings: list[dict], model: str) -> dict:
    """One fresh tool-less process for an action's group; labels maps each rule to its label id. Returns
    {label: adjudication}, every adjudication carrying the one prompt's sha256."""
    adj = core.heldout()["matching"]["adjudicator"]
    proto = core.protocol()["matching"]["adjudicator"]
    prompt = heldout_match_prompt(action, findings)
    argv = _argv(proto["invocation"], adj["system_prompt"], model)
    ids = {f["id"] for f in findings}
    attempts, ans = [], None
    for _ in range(2):
        d = Path(tempfile.mkdtemp(prefix="match-", dir="/tmp"))
        try:
            p = subprocess.run(argv, input=prompt, capture_output=True, text=True, cwd=str(d), timeout=600,
                               env=_env(["CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD", "CLAUDE_ADDITIONAL_DIRECTORIES"]))
            out = p.stdout
        except subprocess.TimeoutExpired:
            out = ""
        shutil.rmtree(d, ignore_errors=True)
        try:
            cli = json.loads(out)
        except json.JSONDecodeError:
            cli = {}
        if cli:
            _check_model("A", cli)
        res = cli.get("result") or ""
        got = None
        m = re.search(r"\{.*\}", res, re.S)
        if m:
            try:
                got = json.loads(m.group(0))
            except json.JSONDecodeError:
                got = None
        v = got.get("violates") if isinstance(got, dict) else None
        ok = isinstance(v, dict) and all(isinstance(v.get(r, []), list) and all(isinstance(x, str) for x in v.get(r, []))
                                         for r in RULES)
        attempts.append({"is_error": cli.get("is_error"), "num_turns": cli.get("num_turns"), "result": res[-4000:],
                         "outcome": "ok" if ok else "unparsable"})
        if ok:
            ans = v
            break
    sha = core.sha256_text(prompt)
    return {lab: {"label": lab, "findings": sorted(ids), "confirmed": sorted(set((ans or {}).get(r, [])) & ids),
                  "prompt_sha256": sha, "attempts": attempts} for r, lab in labels.items()}
