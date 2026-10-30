"""The coordinator (whitepaper §9.1: "one coordinator is the human's only window into the system"; BUILD_PLAN I45 and
row I87; §0.2: a session's prompt is written by the human or rendered by the coordinator). The contract is the
docstring of tests_m3/test_audit_loop.py, "Coordinator".

    python -m holon coordinator status [--root R] [--out PATH] [--check]
        docs/STATUS.md from every spec/M*/predictions.json with iteration keys, prompts/, docs/iterations/ and
        results/M*/audit_status.json. It reads files only (no git, no clock, no environment, no checker), so it renders
        in well under a second; --check writes nothing and exits 0 iff the file is byte-identical. Every merge that
        adds a key, a prompt, a report or an audit status makes the file stale: whoever merges re-renders it.
    python -m holon coordinator prompt --key I<n> [--root R] [--out PATH]
        a session prompt from docs/BUILD_PLAN.md: the iteration's §4 section ("#### I<n>. ..." up to the next heading)
        when there is one, else its §3 map row, verbatim, under the standard preamble. Default output
        prompts/I<n>_<slug>.md; it refuses (exit 2) to write over any existing prompt of the key.
    python -m holon coordinator audit-prompt --milestone M --round n --type A<k> [--root R] [--out PATH]
        an auditor's prompt from audit/prompts/round.md and audit/prompts/A<k>.md, filled from the round's packet
        (audit/rounds/<M>/round<n>/packet.json).

Nothing here names a law or a target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = Path("docs") / "STATUS.md"
TITLE_MAX = 120
_KEY = re.compile(r"^I([0-9]+)$")


# ====================================================================== status
def _json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _cell(s) -> str:
    return str(s).replace("\n", " ").replace("|", "\\|")


def first_sentence(title: str) -> str:
    t = " ".join(str(title).split())
    i = t.find(". ")
    if i >= 0:
        t = t[: i + 1]
    return t if len(t) <= TITLE_MAX else t[: TITLE_MAX - 1] + "…"


def _key_order(k: str) -> tuple:
    m = _KEY.match(k)
    return (0, int(m.group(1)), k) if m else (1, 0, k)


def _milestone_order(m: str) -> tuple:
    return (int(m[1:]), m) if m[1:].isdigit() else (1 << 30, m)


def predictions_files(root: Path) -> list[tuple[str, Path, dict]]:
    out = []
    for p in sorted((Path(root) / "spec").glob("M*/predictions.json")):
        try:
            doc = _json(p)
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and isinstance(doc.get("iterations"), dict):
            out.append((str(doc.get("milestone") or p.parent.name), p, doc))
    return sorted(out, key=lambda x: _milestone_order(x[0]))


def _prompt_of(root: Path, key: str, item: dict) -> str | None:
    p = item.get("prompt")
    if isinstance(p, str) and (Path(root) / p).is_file():
        return p
    found = sorted((Path(root) / "prompts").glob(f"{key}_*.md")) + sorted((Path(root) / "prompts").glob(f"{key}.md"))
    return found[0].relative_to(root).as_posix() if found else None


def render_status(root: Path) -> str:
    root = Path(root)
    files = predictions_files(root)
    rows, keys, per_m = [], set(), []
    for m, _p, doc in files:
        its = doc["iterations"]
        n_rep = 0
        for key in sorted(its, key=_key_order):
            it = its[key] if isinstance(its[key], dict) else {}
            keys.add(key)
            rep = Path("docs") / "iterations" / f"{key}.md"
            has_rep = (root / rep).is_file()
            n_rep += int(has_rep)
            prompt = _prompt_of(root, key, it)
            rows.append((_key_order(key), _milestone_order(m),
                         f"| {key} | {m} | {_cell(first_sentence(it.get('title', '')))} | "
                         f"{'`' + prompt + '`' if prompt else 'none'} | {len(it.get('predictions') or [])} | "
                         f"{len(it.get('regressions') or [])} | {len(it.get('tests') or [])} | "
                         f"{'`' + rep.as_posix() + '`' if has_rep else 'none'} |"))
        per_m.append((m, len(its), sum(len((v or {}).get("predictions") or []) for v in its.values()),
                      sum(len((v or {}).get("regressions") or []) for v in its.values()), n_rep))
    out = ["# HOLON status", "",
           "Rendered by `python -m holon coordinator status` (holon/coordinator.py, I87) from every "
           "`spec/M*/predictions.json`, `prompts/`, `docs/iterations/` and `results/M*/audit_status.json`. Do not edit "
           "it: edit those and re-render. `--check` fails on any difference, so whoever merges a new key, prompt, "
           "report or audit status re-renders it.", "",
           "## Milestones", "",
           "| Milestone | Keys | Predictions | Regressions | Reports |", "|---|---|---|---|---|"]
    out += [f"| {m} | {k} | {p} | {r} | {n} |" for m, k, p, r, n in per_m]
    out += ["", "## Audit loop (whitepaper §9.5; results/<M>/audit_status.json)", ""]
    st = []
    for p in sorted((root / "results").glob("M*/audit_status.json"), key=lambda q: _milestone_order(q.parent.name)):
        try:
            d = _json(p)
        except (OSError, ValueError):
            continue
        st.append(f"| {_cell(d.get('milestone'))} | {'yes' if d.get('converged') else 'no'} | {d.get('streak')} | "
                  f"{d.get('k')} | {d.get('counted')} | {len(d.get('rounds') or [])} | "
                  f"{_cell(', '.join(d.get('open_high') or []) or 'none')} | {_cell(d.get('why', ''))} |")
    if st:
        out += ["| Milestone | Converged | Streak | k | Counted rounds | Rounds | Open high findings | Why |",
                "|---|---|---|---|---|---|---|---|"] + st
    else:
        out.append("No milestone has an audit status yet.")
    out += ["", "## Iterations", "",
            "| Key | Milestone | Title | Prompt | Predictions | Regressions | Tests | Report |",
            "|---|---|---|---|---|---|---|---|"]
    out += [r for _k, _m, r in sorted(rows, key=lambda x: (x[0], x[1]))]
    others = sorted((p.stem for p in (root / "docs" / "iterations").glob("*.md") if p.stem not in keys),
                    key=_key_order) if (root / "docs" / "iterations").is_dir() else []
    out += ["", "## Reports without a predictions key", ""]
    out.append(", ".join(f"`docs/iterations/{s}.md`" for s in others) if others else "None.")
    return "\n".join(out) + "\n"


# ====================================================================== prompts
def plan_entry(plan: str, key: str) -> tuple[str, str, str] | None:
    """(title, verbatim text, where) of a key in BUILD_PLAN: its §4 section, else its §3 map row."""
    m = re.search(rf"(?ms)^#### {re.escape(key)}\. .*?(?=^#{{2,4}} )", plan)
    if m:
        sec = m.group(0).strip()
        head = sec.splitlines()[0][len(f"#### {key}. "):]
        title = re.sub(r"\s*\(about [^)]*\)\s*$", "", head).strip()
        return title, sec, f"§4, \"#### {key}.\""
    row = next((ln for ln in plan.splitlines() if ln.startswith(f"| {key} |")), None)
    if row is None:
        return None
    cols = [c.strip() for c in row.strip().strip("|").split(" | ")]
    text = cols[2] if len(cols) > 2 else row
    b = re.match(r"\*\*(.*?)\*\*", text)
    title = (b.group(1) if b else text).strip()
    title = re.sub(r"^=\s*[^:]*:\s*", "", title).rstrip(".")
    return title, row.strip(), f"§3, the map row {key}"


def slug(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return "_".join(words[:3]) or "session"


PREAMBLE = """# ${key}: ${title}

Rendered by `python -m holon coordinator prompt --key ${key}` (holon/coordinator.py) from `docs/BUILD_PLAN.md`
(${where}). The human may edit it before the session starts; the key's prereg names it.

Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, then this prompt (AGENTS.md, "Read first"), and
run `bend guide`: Bend 2 is newer than your training data.

Protocol (BUILD_PLAN §0.1 and §0.2):
1. Prereg first. Write the key `${key}` into `spec/<M>/predictions.json` (predictions, regressions, outcome_paths,
   tests, thresholds) with this prompt, the acceptance tests (red) and every instrument that decides a prediction, in
   one commit. `python -m holon audit prereg --milestone <M>` must print PREREG OK. Push it before any implementation.
2. Build. A fix goes into a generator, never into a generated file; outputs are byte-identical across runs; no frozen
   file is edited and no claim is weakened (AGENTS.md rules 1-4).
3. Report. `docs/iterations/${key}.md` states each prediction held or missed with its evidence, and ends with Done,
   Surprises, Questions for the human and Not done.

## The plan's text

${text}
"""


def render_prompt(root: Path, key: str) -> tuple[str, str]:
    """(text, default output path relative to the root)."""
    plan = (Path(root) / "docs" / "BUILD_PLAN.md").read_text(encoding="utf-8")
    e = plan_entry(plan, key)
    if e is None:
        raise KeyError(f"docs/BUILD_PLAN.md has no section and no map row for {key}")
    title, text, where = e
    out = string.Template(PREAMBLE).safe_substitute(key=key, title=title, where=where, text=text)
    return out, f"prompts/{key}_{slug(title)}.md"


def existing_prompts(root: Path, key: str) -> list[Path]:
    d = Path(root) / "prompts"
    return sorted(d.glob(f"{key}_*.md")) + sorted(d.glob(f"{key}.md")) if d.is_dir() else []


# ====================================================================== auditor prompts
def render_audit_prompt(root: Path, milestone: str, rnd: int, typ: str) -> str:
    root = Path(root)
    pk_rel = f"audit/rounds/{milestone}/round{rnd}/packet.json"
    pk_path = root / pk_rel
    if not pk_path.is_file():
        raise FileNotFoundError(f"{pk_rel} does not exist: run `holon audit hostile --milestone {milestone} --round "
                                f"{rnd} --target <commit>` first")
    raw = pk_path.read_bytes()
    pk = json.loads(raw)
    aud = (pk.get("auditors") or {}).get(typ)
    if aud is None:
        raise KeyError(f"the packet has no auditor {typ}")
    tg = aud.get("targets")
    n = sum(len(v) for v in tg.values()) if isinstance(tg, dict) and all(isinstance(v, list) for v in tg.values()) \
        else (len(tg) if isinstance(tg, (list, dict)) else 0)
    fields = {"milestone": milestone, "round": str(rnd), "type": typ, "name": aud.get("name", ""),
              "what": aud.get("what", ""), "packet": pk_rel, "packet_sha256": hashlib.sha256(raw).hexdigest(),
              "target_commit": pk.get("target_commit", ""), "targets": str(n), "laws": str(len(pk.get("laws") or {}))}
    parts = []
    for name in ("round.md", f"{typ}.md"):
        p = root / "audit" / "prompts" / name
        if not p.is_file():
            p = ROOT / "audit" / "prompts" / name
        parts.append(string.Template(p.read_text(encoding="utf-8")).safe_substitute(fields))
    return "\n".join(x.rstrip("\n") + "\n" for x in parts)


# ====================================================================== the CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon coordinator", description=__doc__.split("\n\n")[0])
    ap.add_argument("what", choices=["status", "prompt", "audit-prompt"])
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true", help="status: write nothing; exit 0 iff the file is current")
    ap.add_argument("--key")
    ap.add_argument("--milestone")
    ap.add_argument("--round", type=int)
    ap.add_argument("--type", choices=["A1", "A2", "A3", "A4"])
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    if a.what == "status":
        text = render_status(root)
        out = Path(a.out) if a.out else root / STATUS
        if a.check:
            if not out.is_file() or out.read_text(encoding="utf-8") != text:
                print(f"coordinator: {out} is not the rendering of the current files: run `python -m holon coordinator "
                      "status`", file=sys.stderr)
                return 1
            print("coordinator: docs/STATUS.md is current")
            return 0
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"coordinator: wrote {out}")
        return 0
    if a.what == "prompt":
        if not a.key or not _KEY.match(a.key):
            print("coordinator: --key I<n> is required", file=sys.stderr)
            return 2
        try:
            text, default = render_prompt(root, a.key)
        except KeyError as e:
            print(f"coordinator: {e.args[0]}", file=sys.stderr)
            return 2
        out = Path(a.out).resolve() if a.out else root / default
        mine = {p.resolve() for p in existing_prompts(root, a.key)}
        if (not a.out and mine) or out in mine:
            print(f"coordinator: {a.key} already has a prompt ({', '.join(sorted(p.name for p in mine))}); a prompt is "
                  "written once, before its session, and the coordinator never writes over it", file=sys.stderr)
            return 2
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"coordinator: wrote {out}")
        return 0
    if not (a.milestone and a.round and a.type):
        print("coordinator: audit-prompt needs --milestone, --round and --type", file=sys.stderr)
        return 2
    try:
        text = render_audit_prompt(root, a.milestone, a.round, a.type)
    except (FileNotFoundError, KeyError) as e:
        print(f"coordinator: {e.args[0]}", file=sys.stderr)
        return 2
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"coordinator: wrote {a.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
