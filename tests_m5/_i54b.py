"""I54b's instrument: the corpus-truth key's packet generator, answer recorder, frozen-invocation runner and collector.

It implements spec/M5/lib/truth_protocol.json (frozen at I54's prereg) and nothing more, for the 20 entries of I48's
corpus (spec/eval/corpus.json). It is the tool the coordinator runs, and the reference the contract tests
(tests_m5/test_m5_truth_key.py) check, so the collector is pinned by sha256 before any labeller answers and cannot follow
the labels. It imports nothing from holon/ or tools/, and it never reads a HOLON output: the truth reads only the
corpus's verbatim text (truth_protocol.json doc).

  python -m tests_m5._i54b packets [--check]
      spec/M5/truth/packets/<id>.<role>.txt, one per (entry, labeller), and packets/index.json. A packet is the exact
      message a labeller receives: the pinned prompt with {{TEXT}} replaced by the entry's text (title, a newline, the
      description, verbatim). Nothing else.
  python -m tests_m5._i54b answer --family same|different --invocation cloud_session|external --entry ID --role a|b
                                  (--response-file FILE | --no-response) [--session NAME]
      appends one attempt to spec/M5/truth/answers/<family>/<id>.<role>.json: the labeller's final message verbatim
      (or no message at all), under the retry rule.
  python -m tests_m5._i54b run --role a|b --model NAME [--entries ID ...]
      the frozen invocation (spec/M4/lib/corpus_protocol.json labelling_invocation, unchanged): one fresh tool-less
      `claude -p` process per packet, the packet on stdin, family same. The model name is kept outside the repository
      (STORE), never written to it.
  python -m tests_m5._i54b collect --family same|different [--check]
      validates every answer file against the schema and the pins, applies Q1-Q3 and the derivations, and writes
      spec/M5/truth/corpus.json (same; the protocol's output path) or corpus_different.json, with a run sidecar
      (corpus.run.json, corpus_different.run.json). It refuses, writing nothing, on any problem or missing answer.
  python -m tests_m5._i54b compare [--check]
      spec/M5/truth/family_comparison.json: the same-family and different-family truths side by side, never pooled.
  python -m tests_m5._i54b status
      which answer files exist and which attempts they still need.

Every file is json.dumps(obj, indent=2, sort_keys=True) + newline; sorted iteration; no timestamps. Exit 0 written or
unchanged, 1 a refusal or a --check difference, 2 a usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = "I54b"
KEY_FILE = "spec/M5/predictions/I54b.json"
PROTOCOL = "spec/M5/lib/truth_protocol.json"
PROMPT = "spec/M5/lib/truth_prompt.md"
SCHEMA = "spec/M5/lib/truth_labels.schema.json"
CORPUS = "spec/eval/corpus.json"
INVOCATION_SOURCE = "spec/M4/lib/corpus_protocol.json"
TRUTH = "spec/M5/truth"
PACKETS = "spec/M5/truth/packets"
ANSWERS = "spec/M5/truth/answers"
SLOT = "{{TEXT}}"
ROLES = ("a", "b")
TAGS = {"a": "A", "b": "B"}
FAMILIES = ("same", "different")
INVOCATIONS = {"same": ("cli", "cloud_session"), "different": ("external",)}
QUESTIONS = ("actor_flow", "doc_contradiction", "trigger")
ANSWER_KEYS = ("quote", "value")
OUTPUTS = {"same": ("corpus.json", "corpus.run.json"), "different": ("corpus_different.json",
                                                                     "corpus_different.run.json")}
COMPARISON = "family_comparison.json"
UNCOUNTED = ("cli_error", "no_response")      # the process or session gave no answer: retried, never counted
COUNTED = ("turns", "unparsable", "invalid")  # a model output that is not an answer: one more counted attempt
MAX_UNCOUNTED = 5
MAX_COUNTED = 2
RETRY_WAIT = 60
STORE = Path.home() / ".holon" / "eval" / "truth_labellers.json"   # tag -> model, outside the repository
_WS = re.compile(r"\s+")


class Refused(Exception):
    """The input is not what the key pins; nothing is written."""


# ---------------------------------------------------------------------------------------------- files
def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(t: str) -> str:
    return sha256_bytes(t.encode("utf-8"))


def file_sha256(root: Path, rel: str) -> str:
    return sha256_bytes((root / rel).read_bytes())


def load(root: Path, rel: str):
    return json.loads((root / rel).read_text(encoding="utf-8"))


def protocol(root: Path) -> dict:
    return load(root, PROTOCOL)


def key(root: Path) -> dict:
    return load(root, KEY_FILE)


def pins(root: Path) -> dict:
    return key(root)["thresholds"]["pins"]


def schema(root: Path) -> dict:
    return load(root, SCHEMA)


# ---------------------------------------------------------------------------------------------- texts and packets
def entries(root: Path) -> list[dict]:
    """The corpus entries, by id."""
    return sorted(load(root, CORPUS)["entries"], key=lambda e: e["id"])


def entry_text(entry: dict) -> str:
    """truth_protocol.json inputs.text: the entry's title, a newline, then its description, verbatim."""
    return entry["title"] + "\n" + entry["description"]


def render_packet(template: str, text: str) -> str:
    """The prompt with its one {{TEXT}} slot replaced by the text, in one pass (the text is never scanned again)."""
    if template.count(SLOT) != 1:
        raise Refused(f"{PROMPT} holds {template.count(SLOT)} {SLOT} slots, not exactly one")
    i = template.index(SLOT)
    return template[:i] + text + template[i + len(SLOT):]


def packet_name(entry_id: str, role: str) -> str:
    return f"{entry_id}.{role}"


def packet_rel(entry_id: str, role: str) -> str:
    return f"{PACKETS}/{packet_name(entry_id, role)}.txt"


def texts(root: Path) -> dict[str, str]:
    return {e["id"]: entry_text(e) for e in entries(root)}


def packets(root: Path) -> dict[str, str]:
    """{<id>.<role>: packet text} for every entry and labeller."""
    tpl = (root / PROMPT).read_text(encoding="utf-8")
    return {packet_name(i, r): render_packet(tpl, t) for i, t in texts(root).items() for r in ROLES}


def computed_pins(root: Path) -> dict:
    """The pins the key holds, recomputed from the frozen inputs (the key is written from this, never by hand)."""
    return {"corpus_sha256": file_sha256(root, CORPUS), "protocol_sha256": file_sha256(root, PROTOCOL),
            "prompt_sha256": file_sha256(root, PROMPT), "schema_sha256": file_sha256(root, SCHEMA),
            "invocation_source_sha256": file_sha256(root, INVOCATION_SOURCE),
            "texts": {i: sha256_text(t) for i, t in texts(root).items()},
            "packets": {n: sha256_text(t) for n, t in packets(root).items()}}


def check_inputs(root: Path) -> list[str]:
    """The frozen inputs still hash to the key's pins."""
    p, c = pins(root), computed_pins(root)
    return [f"{k}: {c[k]} is not the pinned {p.get(k)}" for k in sorted(c) if c[k] != p.get(k)]


def packet_index(root: Path) -> dict:
    p = pins(root)
    return {"key": KEY, "corpus_sha256": p["corpus_sha256"], "protocol_sha256": p["protocol_sha256"],
            "prompt_sha256": p["prompt_sha256"],
            "packets": [{"entry": n.split(".")[0], "role": n.split(".")[1], "path": f"{PACKETS}/{n}.txt",
                         "sha256": h, "text_sha256": p["texts"][n.split(".")[0]]}
                        for n, h in sorted(p["packets"].items())]}


def packet_files(root: Path) -> dict[str, str]:
    probs = check_inputs(root)
    if probs:
        raise Refused("; ".join(probs))
    out = {f"{PACKETS}/{n}.txt": t for n, t in sorted(packets(root).items())}
    out[f"{PACKETS}/index.json"] = dumps(packet_index(root))
    return out


def write_files(root: Path, files: dict[str, str], check: bool, directory: str | None = None) -> list[str]:
    """Write (or with check, compare) files; with directory, a file there that files does not name is a difference."""
    diffs = []
    if directory is not None and (root / directory).is_dir():
        have = sorted(p.relative_to(root).as_posix() for p in (root / directory).iterdir() if p.is_file())
        diffs += [f"{p}: not generated" for p in have if p not in files]
    for rel, text in sorted(files.items()):
        p = root / rel
        cur = p.read_bytes() if p.is_file() else None
        if cur != text.encode("utf-8"):
            diffs.append(f"{rel}: {'differs' if cur is not None else 'missing'}")
            if not check:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(text.encode("utf-8"))
    return diffs


# ---------------------------------------------------------------------------------------------- one answer
def parse_response(text: str):
    """The answer a verbatim final message gives (I48's parse_response): the JSON object of the whole message
    (surrounding whitespace aside), or of the text between a first line ``` (or ```json) and a last line ```."""
    t = text.strip()
    lines = t.split("\n")
    if len(lines) >= 2 and lines[0].strip() in ("```", "```json") and lines[-1].strip() == "```":
        t = "\n".join(lines[1:-1])
    obj = json.loads(t)
    if not isinstance(obj, dict):
        raise ValueError("the response is not a JSON object")
    return obj


def answer_ok(obj) -> bool:
    """truth_protocol.json answer, its shape only: exactly the three questions, each exactly {value, quote}, value a
    string and quote a string or null. A value outside its list is not a shape error: Q1 makes it undocumented."""
    if not isinstance(obj, dict) or sorted(obj) != list(QUESTIONS):
        return False
    for q in QUESTIONS:
        a = obj[q]
        if not (isinstance(a, dict) and sorted(a) == list(ANSWER_KEYS) and isinstance(a["value"], str)
                and (a["quote"] is None or isinstance(a["quote"], str))):
            return False
    return True


def _response_outcome(r) -> str:
    if not isinstance(r, str):
        return "unparsable"
    try:
        obj = parse_response(r)
    except (ValueError, RecursionError):
        return "unparsable"
    return "ok" if answer_ok(obj) else "invalid"


def cli_outcome(cli) -> str:
    """One attempt of the frozen invocation (I48's attempt_outcome with this protocol's answer): ok iff is_error is
    false, num_turns is the integer 1 and result parses to an answer_ok object; else the first failing of cli_error,
    turns, unparsable and invalid."""
    if not isinstance(cli, dict) or cli.get("is_error") is not False:
        return "cli_error"
    n = cli.get("num_turns")
    if type(n) is not int or n != 1:
        return "turns"
    return _response_outcome(cli.get("result"))


def session_outcome(response) -> str:
    """One attempt of a session (cloud_session or external): no_response when it gave no final message, else as the
    final message parses."""
    return "no_response" if response is None else _response_outcome(response)


def attempt_outcome(invocation: str, attempt: dict) -> str:
    return cli_outcome(attempt.get("cli")) if invocation == "cli" else session_outcome(attempt.get("response"))


def retry_follows(outcomes: list[str]) -> bool:
    """I48's retry rule over one packet's attempts, in order: an uncounted attempt (cli_error, no_response) is run
    again, at most 5 per packet; a counted one (turns, unparsable, invalid) is followed by exactly one more counted
    attempt. The attempts stop at the first ok one, the second counted one or the fifth uncounted one, and only
    there."""
    counted = unc = 0
    for i, o in enumerate(outcomes):
        last = i == len(outcomes) - 1
        if o == "ok":
            return last
        if o in UNCOUNTED:
            unc += 1
            stop = unc == MAX_UNCOUNTED
        elif o in COUNTED:
            counted += 1
            stop = counted == MAX_COUNTED
        else:
            return False
        if stop != last:
            return False
    return bool(outcomes)


def finished(outcomes: list[str]) -> bool:
    """No further attempt may follow."""
    return bool(outcomes) and (outcomes[-1] == "ok" or sum(o in COUNTED for o in outcomes) == MAX_COUNTED
                               or sum(o in UNCOUNTED for o in outcomes) == MAX_UNCOUNTED)


def collapse(s: str) -> str:
    """Q2: runs of whitespace (Python's Unicode \\s) collapsed to one space; nothing is stripped."""
    return _WS.sub(" ", s)


def check_answer(values: list[str], a: dict, text: str) -> tuple[str, str | None]:
    """Q1-Q2 for one question's answer {value, quote}: (the value that stands, or undocumented; the rule that failed)."""
    v, q = a["value"], a["quote"]
    if v not in values:
        return "undocumented", "Q1"
    if v == "undocumented":
        return "undocumented", (None if q is None else "Q1")
    if not isinstance(q, str) or collapse(q) not in collapse(text):
        return "undocumented", "Q2"
    return v, None


def checked(proto: dict, answer: dict | None, text: str) -> dict | None:
    if answer is None:
        return None
    out = {}
    for q in QUESTIONS:
        v, fail = check_answer(proto["questions"][q]["values"], answer[q], text)
        out[q] = {"value": answer[q]["value"], "quote": answer[q]["quote"], "checked": v, "fails": fail}
    return out


def final(ca: dict | None, cb: dict | None) -> dict:
    """Q3: an answer stands only when a and b give the same value and both pass Q1-Q2; otherwise undocumented."""
    out = {}
    for q in QUESTIONS:
        ok = (ca is not None and cb is not None and ca[q]["fails"] is None and cb[q]["fails"] is None
              and ca[q]["value"] == cb[q]["value"])
        out[q] = ca[q]["value"] if ok else "undocumented"
    return out


def derive_l6(f: dict) -> str:
    """truth_protocol.json derived.l6."""
    t, a = f["trigger"], f["actor_flow"]
    if t == "untrusted" and a in ("gain", "none"):
        return "rational"
    if t in ("trusted_only", "none") or (t == "untrusted" and a == "loss"):
        return "irrational"
    return "undocumented"


def derive_l10(f: dict) -> str:
    """truth_protocol.json derived.l10."""
    return f["doc_contradiction"] if f["doc_contradiction"] in ("yes", "no") else "undocumented"


# ---------------------------------------------------------------------------------------------- answer files
def answer_rel(family: str, entry_id: str, role: str) -> str:
    return f"{ANSWERS}/{family}/{entry_id}.{role}.json"


def new_answer_file(root: Path, family: str, invocation: str, entry_id: str, role: str) -> dict:
    p = pins(root)
    name = packet_name(entry_id, role)
    if name not in p["packets"]:
        raise Refused(f"no pinned packet {name}")
    if family not in FAMILIES or invocation not in INVOCATIONS[family]:
        raise Refused(f"invocation {invocation} is not one of family {family}'s {list(INVOCATIONS.get(family, ()))}")
    return {"key": KEY, "entry": entry_id, "role": role, "family": family, "model_tag": TAGS[role],
            "invocation": invocation, "packet": packet_rel(entry_id, role), "packet_sha256": p["packets"][name],
            "attempts": [], "answer": None}


def add_attempt(doc: dict, attempt: dict) -> dict:
    """Append one attempt (outcome computed here) and set answer; refuses an attempt the retry rule does not allow."""
    outs = [a["outcome"] for a in doc["attempts"]]
    if finished(outs):
        raise Refused(f"{doc['entry']}.{doc['role']}: the retry rule allows no further attempt after {outs}")
    att = dict(attempt)
    att["outcome"] = attempt_outcome(doc["invocation"], att)
    doc["attempts"].append(att)
    doc["answer"] = answer_of(doc)
    return doc


def answer_of(doc: dict):
    """The answer is the last attempt's when it is ok, else null."""
    if not doc["attempts"] or doc["attempts"][-1]["outcome"] != "ok":
        return None
    last = doc["attempts"][-1]
    return parse_response(last["cli"]["result"] if doc["invocation"] == "cli" else last["response"])


def session_attempt(response: str | None, session: str | None) -> dict:
    return {"cli": None, "response": response, "session": session}


def validate_answer_file(root: Path, rel: str, doc, sch: dict) -> list[str]:
    """Every rule an answer file must pass before the collector reads it."""
    from tests.reference import mini_schema   # stdlib-only validator, frozen
    errs = [f"{rel}: {e}" for e in mini_schema.errors(doc, {**sch, "$ref": "#/$defs/answer_file"})]
    if errs:
        return errs
    m = re.fullmatch(rf"{ANSWERS}/(same|different)/(c\d\d)\.(a|b)\.json", rel)
    p = pins(root)
    if not m:
        return [f"{rel}: not an answer path"]
    fam, eid, role = m.groups()
    name = packet_name(eid, role)
    if (doc["family"], doc["entry"], doc["role"]) != (fam, eid, role):
        errs.append(f"{rel}: family/entry/role {doc['family']}/{doc['entry']}/{doc['role']} do not match the path")
    if doc["model_tag"] != TAGS[role]:
        errs.append(f"{rel}: model_tag {doc['model_tag']} is not role {role}'s {TAGS[role]}")
    if doc["invocation"] not in INVOCATIONS[fam]:
        errs.append(f"{rel}: invocation {doc['invocation']} is not one of family {fam}'s")
    if name not in p["packets"]:
        return errs + [f"{rel}: no pinned packet {name}"]
    if doc["packet"] != packet_rel(eid, role):
        errs.append(f"{rel}: packet {doc['packet']} is not {packet_rel(eid, role)}")
    if doc["packet_sha256"] != p["packets"][name]:
        errs.append(f"{rel}: packet_sha256 is not the pinned {p['packets'][name]}")
    pk = root / packet_rel(eid, role)
    if not pk.is_file() or sha256_bytes(pk.read_bytes()) != p["packets"][name]:
        errs.append(f"{rel}: the packet file {packet_rel(eid, role)} does not hash to the pin")
    outs = []
    for i, a in enumerate(doc["attempts"]):
        if (doc["invocation"] == "cli") != (a["cli"] is not None):
            errs.append(f"{rel}: attempt {i}: cli is {'missing' if a['cli'] is None else 'present'} for invocation "
                        f"{doc['invocation']}")
            continue
        if doc["invocation"] == "cli" and a["response"] != a["cli"].get("result"):
            errs.append(f"{rel}: attempt {i}: response is not the CLI's result")
        o = attempt_outcome(doc["invocation"], a)
        if o != a["outcome"]:
            errs.append(f"{rel}: attempt {i}: outcome {a['outcome']} recomputes to {o}")
        outs.append(o)
    if errs:
        return errs
    if not retry_follows(outs):
        errs.append(f"{rel}: attempts {outs} do not follow the retry rule (or are unfinished)")
    elif doc["answer"] != answer_of(doc):
        errs.append(f"{rel}: answer is not the last ok attempt's parsed message")
    return errs


def read_answers(root: Path, family: str) -> tuple[dict, list[str]]:
    """{(entry, role): answer file} of a family, and every problem (a missing file is one)."""
    sch, docs, probs = schema(root), {}, []
    d = root / ANSWERS / family
    want = {answer_rel(family, e, r) for e in pins(root)["texts"] for r in ROLES}
    have = sorted(p.relative_to(root).as_posix() for p in d.iterdir()) if d.is_dir() else []
    probs += [f"{p}: not an answer file of a pinned packet" for p in have if p not in want]
    for rel in sorted(want):
        if not (root / rel).is_file():
            probs.append(f"{rel}: missing")
            continue
        try:
            doc = json.loads((root / rel).read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            probs.append(f"{rel}: not JSON ({e})")
            continue
        errs = validate_answer_file(root, rel, doc, sch)
        probs += errs
        if not errs:
            docs[(doc["entry"], doc["role"])] = doc
    return docs, probs


# ---------------------------------------------------------------------------------------------- collection
def collect(root: Path, family: str) -> dict[str, str]:
    """The truth file and its run sidecar of a family; raises Refused on any problem (nothing is written)."""
    if family not in FAMILIES:
        raise Refused(f"no family {family}")
    probs = check_inputs(root)
    docs, ap = read_answers(root, family)
    probs += ap
    if probs:
        raise Refused("\n".join(probs))
    proto, txt, p = protocol(root), texts(root), pins(root)
    out, run = {}, {}
    disagreements, fails, empty = [], [], []
    for eid in sorted(txt):
        ca = checked(proto, docs[(eid, "a")]["answer"], txt[eid])
        cb = checked(proto, docs[(eid, "b")]["answer"], txt[eid])
        f = final(ca, cb)
        out[eid] = {"answers": {"a": ca, "b": cb}, "final": f, "l6": derive_l6(f), "l10": derive_l10(f)}
        for q in QUESTIONS:
            va = None if ca is None else ca[q]["value"]
            vb = None if cb is None else cb[q]["value"]
            if va != vb:
                disagreements.append({"entry": eid, "question": q, "a": va, "b": vb})
            for r, c in (("a", ca), ("b", cb)):
                if c is not None and c[q]["fails"] is not None:
                    fails.append({"entry": eid, "question": q, "role": r, "rule": c[q]["fails"],
                                  "value": c[q]["value"]})
                if c is not None and isinstance(c[q]["quote"], str) and not c[q]["quote"].strip():
                    empty.append({"entry": eid, "question": q, "role": r})
        run[eid] = {r: {"invocation": docs[(eid, r)]["invocation"],
                        "outcomes": [a["outcome"] for a in docs[(eid, r)]["attempts"]],
                        "answered": docs[(eid, r)]["answer"] is not None,
                        "file_sha256": file_sha256(root, answer_rel(family, eid, r))} for r in ROLES}
    truth = {"protocol_sha256": p["protocol_sha256"], "corpus_sha256": p["corpus_sha256"], "entries": out}
    tname, rname = OUTPUTS[family]
    tally = {}
    for k in ("l6", "l10"):
        tally[k] = {}
        for eid, e in out.items():
            tally[k][e[k]] = tally[k].get(e[k], 0) + 1
    invs = sorted({d["invocation"] for d in docs.values()})
    sidecar = {"key": KEY, "family": family, "truth": f"{TRUTH}/{tname}", "truth_sha256": sha256_text(dumps(truth)),
               "prompt_sha256": p["prompt_sha256"], "schema_sha256": p["schema_sha256"],
               "invocations": invs, "protocol_exact_invocation": invs == ["cli"],
               "model_check": "observed (the CLI's modelUsage, per tag)" if invs == ["cli"]
               else "declared by the launcher, not observed",
               "known_exclusions": sorted(proto["known_exclusions"]),
               "disagreements": disagreements, "rule_failures": fails, "empty_quotes": empty, "tally": tally, "attempts": run}
    return {f"{TRUTH}/{tname}": dumps(truth), f"{TRUTH}/{rname}": dumps(sidecar)}


def compare(root: Path) -> dict[str, str]:
    """The two families' truths side by side, per entry and per question; never pooled into one truth."""
    s = load(root, f"{TRUTH}/{OUTPUTS['same'][0]}")
    d = load(root, f"{TRUTH}/{OUTPUTS['different'][0]}")
    for fam in FAMILIES:   # each truth must be what its answers give
        files = collect(root, fam)
        for rel, text in files.items():
            if (root / rel).read_text(encoding="utf-8") != text:
                raise Refused(f"{rel} is not what its answers give: run collect --family {fam}")
    rows, counts = [], {}
    for eid in sorted(s["entries"]):
        es, ed = s["entries"][eid], d["entries"][eid]
        row = {"entry": eid}
        for q in QUESTIONS + ("l6", "l10"):
            vs = es["final"][q] if q in QUESTIONS else es[q]
            vd = ed["final"][q] if q in QUESTIONS else ed[q]
            row[q] = {"same": vs, "different": vd}
            c = counts.setdefault(q, {"equal": 0, "differ": 0})
            c["equal" if vs == vd else "differ"] += 1
        rows.append(row)
    doc = {"key": KEY, "same_sha256": file_sha256(root, f"{TRUTH}/{OUTPUTS['same'][0]}"),
           "different_sha256": file_sha256(root, f"{TRUTH}/{OUTPUTS['different'][0]}"),
           "pooled": False, "counts": counts, "entries": rows}
    return {f"{TRUTH}/{COMPARISON}": dumps(doc)}


# ---------------------------------------------------------------------------------------------- the frozen invocation
def invocation(root: Path) -> dict:
    return load(root, INVOCATION_SOURCE)["labelling_invocation"]


def reduce_output(stdout: str | None) -> tuple[dict, dict | None]:
    """The CLI's JSON output reduced to is_error, num_turns, result, session_id and subtype (a missing key is null;
    every key is null when the output is not one JSON object), and the raw object for the model check."""
    keys = ("is_error", "num_turns", "result", "session_id", "subtype")
    try:
        raw = json.loads(stdout) if stdout is not None else None
    except ValueError:
        raw = None
    if not isinstance(raw, dict):
        return {k: None for k in keys}, None
    return {k: raw.get(k) for k in keys}, raw


def run_cli(argv: list[str], prompt: str, env: dict, cwd: str, timeout: int) -> str | None:
    try:
        r = subprocess.run(argv, input=prompt.encode("utf-8"), capture_output=True, env=env, cwd=cwd,
                           timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return r.stdout.decode("utf-8", errors="replace")


def sleep(seconds: float) -> None:   # replaced by a stub in tests
    time.sleep(seconds)


def call(inv: dict, model: str, prompt: str) -> str | None:
    """One fresh process of the frozen invocation: argv with <system_prompt> and <model> filled, the prompt on stdin,
    a fresh empty directory (removed after), the environment without env_removed."""
    argv = [inv["system_prompt"] if a == "<system_prompt>" else model if a == "<model>" else a for a in inv["argv"]]
    env = {k: v for k, v in os.environ.items() if k not in inv["env_removed"]}
    cwd = tempfile.mkdtemp(prefix="label-", dir="/tmp")
    try:
        return run_cli(argv, prompt, env, cwd, inv["timeout_seconds"])
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def reported_models(raw: dict | None) -> list[str]:
    usage = raw.get("modelUsage") if isinstance(raw, dict) else None
    return sorted(usage) if isinstance(usage, dict) else []


def check_model(store: Path, tag: str, raw: dict | None) -> None:
    """one_model_per_role and a_differs_from_b, on the model each call reports (kept in store, never in the repo)."""
    names = reported_models(raw)
    if raw is None or not names:
        return   # a call that reported nothing (a cli_error): nothing to check
    if len(names) != 1:
        raise Refused(f"one_model_per_role: a call reported {len(names)} models, not exactly one")
    seen = json.loads(store.read_text(encoding="utf-8")) if store.is_file() else {}
    if tag in seen and seen[tag] != names[0]:
        raise Refused(f"one_model_per_role: a call of tag {tag} reported another model than its earlier calls")
    if any(t != tag and m == names[0] for t, m in seen.items()):
        raise Refused(f"a_differs_from_b: tag {tag} reported the model of another tag")
    if tag not in seen:
        seen[tag] = names[0]
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(json.dumps(seen, sort_keys=True), encoding="utf-8")


def run(root: Path, role: str, model: str, entry_ids: list[str] | None, store: Path = STORE) -> list[str]:
    """Label every pinned packet of the role (or entry_ids) with the frozen invocation, family same; an answer file
    already finished is left as it is."""
    if check_inputs(root):
        raise Refused("; ".join(check_inputs(root)))
    inv = invocation(root)
    ids = sorted(pins(root)["texts"]) if entry_ids is None else sorted(entry_ids)
    written = []
    for eid in ids:
        rel = answer_rel("same", eid, role)
        path = root / rel
        doc = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else \
            new_answer_file(root, "same", "cli", eid, role)
        if doc["invocation"] != "cli":
            raise Refused(f"{rel}: already holds invocation {doc['invocation']}")
        prompt = (root / packet_rel(eid, role)).read_text(encoding="utf-8")
        if sha256_text(prompt) != doc["packet_sha256"]:
            raise Refused(f"{packet_rel(eid, role)} does not hash to its pin")
        while not finished([a["outcome"] for a in doc["attempts"]]):
            cli, raw = reduce_output(call(inv, model, prompt))
            check_model(store, TAGS[role], raw)
            add_attempt(doc, {"cli": cli, "response": cli["result"], "session": None})
            if doc["attempts"][-1]["outcome"] in UNCOUNTED and not finished([a["outcome"] for a in doc["attempts"]]):
                sleep(RETRY_WAIT)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(dumps(doc), encoding="utf-8")
        written.append(rel)
    return written


def status(root: Path) -> list[str]:
    lines = []
    for fam in FAMILIES:
        for eid in sorted(pins(root)["texts"]):
            for r in ROLES:
                p = root / answer_rel(fam, eid, r)
                if not p.is_file():
                    if fam == "same" or (root / ANSWERS / fam).is_dir():
                        lines.append(f"{fam} {eid}.{r}: no answer yet")
                    continue
                outs = [a["outcome"] for a in json.loads(p.read_text(encoding="utf-8"))["attempts"]]
                lines.append(f"{fam} {eid}.{r}: {'finished' if finished(outs) else 'needs another attempt'} {outs}")
    return lines


# ---------------------------------------------------------------------------------------------- CLI
def main(argv: list[str], root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(prog="python -m tests_m5._i54b", description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("command", choices=["packets", "answer", "run", "collect", "compare", "status"])
    ap.add_argument("--root", type=Path, default=root)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--family", choices=FAMILIES)
    ap.add_argument("--invocation", choices=["cloud_session", "external"])
    ap.add_argument("--entry")
    ap.add_argument("--entries", nargs="+")
    ap.add_argument("--role", choices=ROLES)
    ap.add_argument("--model")
    ap.add_argument("--response-file", type=Path)
    ap.add_argument("--no-response", action="store_true")
    ap.add_argument("--session")
    a = ap.parse_args(argv)
    r = a.root.resolve()
    try:
        if a.command == "packets":
            diffs = write_files(r, packet_files(r), a.check, PACKETS)
            return _report("packets", diffs, a.check)
        if a.command == "collect":
            if a.family is None:
                ap.error("collect needs --family")
            return _report(f"collect {a.family}", write_files(r, collect(r, a.family), a.check), a.check)
        if a.command == "compare":
            return _report("compare", write_files(r, compare(r), a.check), a.check)
        if a.command == "status":
            for line in status(r):
                print(line)
            return 0
        if a.command == "run":
            if a.role is None or not a.model:
                ap.error("run needs --role and --model")
            for rel in run(r, a.role, a.model, a.entries):
                print(f"run: {rel}")
            return 0
        # answer
        if a.family is None or a.invocation is None or a.entry is None or a.role is None:
            ap.error("answer needs --family, --invocation, --entry and --role")
        if (a.response_file is None) == (not a.no_response):
            ap.error("answer needs exactly one of --response-file FILE and --no-response")
        rel = answer_rel(a.family, a.entry, a.role)
        p = r / rel
        doc = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else \
            new_answer_file(r, a.family, a.invocation, a.entry, a.role)
        if doc["invocation"] != a.invocation:
            raise Refused(f"{rel} holds invocation {doc['invocation']}, not {a.invocation}")
        try:
            resp = None if a.no_response else a.response_file.read_bytes().decode("utf-8")
        except UnicodeDecodeError as e:
            raise Refused(f"{a.response_file} is not UTF-8 ({e})")
        add_attempt(doc, session_attempt(resp, a.session))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(dumps(doc), encoding="utf-8")
        outs = [x["outcome"] for x in doc["attempts"]]
        print(f"answer: {rel}: attempt {len(outs)} {outs[-1]}; "
              f"{'finished' if finished(outs) else 'the retry rule needs another fresh session'}")
        return 0
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1


def _report(what: str, diffs: list[str], check: bool) -> int:
    for d in diffs:
        print(f"{what}: {d}" if check else f"{what}: wrote {d.split(':')[0]}")
    if check:
        print(f"{what}: {'CHECK OK' if not diffs else 'CHECK FAILED'}")
        return 1 if diffs else 0
    print(f"{what}: {len(diffs)} file(s) written")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main(sys.argv[1:]))
