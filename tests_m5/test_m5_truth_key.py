"""I54b acceptance tests: the corpus-truth key (BUILD_PLAN §0.1; the lead's review of I54, condition 5).

Contract. Key I54b (spec/M5/predictions/I54b.json) pins, before any labeller answers: the corpus, I54's frozen truth
protocol and prompt, the frozen invocation's source, the labels schema, each entry's verbatim text and each of the 40
packets, by sha256. Instruments fixed at the prereg, pinned in the key (thresholds.instruments): tests_m5/_i54b.py
(packet generator, answer recorder, frozen-invocation runner, collector), spec/M5/lib/truth_labels.schema.json and the
prompt prompts/I54b_m5_truth_key.md.

Rules
  T1 Pins: every frozen input and instrument hashes to the key's pins; the key's pins are what the instrument computes
     from the frozen inputs; the protocol and prompt are I54's own pins (R1, R2).
  T2 Packets: spec/M5/truth/packets/ holds exactly the 40 packets and index.json the instrument writes; each packet is
     the prompt with the entry's text and nothing else; no field of the entry other than its title and description
     reaches a packet unless the verbatim text itself holds it (red until the packets are committed).
  T3 Rules: Q1, Q2 and Q3 and the derivations, on fixtures; each rule can fail.
  T4 Collector: on a fixture tree, deterministic; it refuses, writing nothing, any answer that breaks a pin, the
     schema, the path, the retry rule or the parse; the frozen-invocation runner checks the models per tag.
  T5 Truth: spec/M5/truth/corpus.json is what the collector gives from the committed same-family answers, and a
     different-family truth exists only beside a comparison, never pooled (red until labelled).
  T6 Scope (R3): no file of M0-M4's outputs, spec/eval, a frozen path or I54's frozen M5 inputs changes.
  P1-P5: the predictions, on the same-family truth (red until labelled).
"""
from __future__ import annotations

import io
import itertools
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tests_m5 import _i54b as I
from tests_m5._m5 import ROOT, file_sha256, git, load_json, predictions, validate

KEY = "I54b"
PROTO = load_json(ROOT / I.PROTOCOL)


def key() -> dict:
    return predictions(KEY)


def schema() -> dict:
    return load_json(ROOT / I.SCHEMA)


def sch(name: str) -> dict:
    s = schema()
    return {**s, "$ref": f"#/$defs/{name}"}


def fixture_root() -> Path:
    """A temp tree holding only the inputs the instrument reads, with the committed key."""
    d = Path(tempfile.mkdtemp(prefix="i54b-"))
    for rel in (I.CORPUS, I.PROTOCOL, I.PROMPT, I.SCHEMA, I.INVOCATION_SOURCE, I.KEY_FILE):
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, d / rel)
    I.write_files(d, I.packet_files(d), False, I.PACKETS)
    return d


def text_of(eid: str) -> str:
    return I.texts(ROOT)[eid]


def reply(trigger=("undocumented", None), actor=("undocumented", None), doc=("undocumented", None)) -> str:
    return json.dumps({"trigger": {"value": trigger[0], "quote": trigger[1]},
                       "actor_flow": {"value": actor[0], "quote": actor[1]},
                       "doc_contradiction": {"value": doc[0], "quote": doc[1]}})


def write_answer(root: Path, family: str, eid: str, role: str, responses: list, inv: str = None) -> Path:
    inv = inv or ("cloud_session" if family == "same" else "external")
    doc = I.new_answer_file(root, family, inv, eid, role)
    for r in responses:
        I.add_attempt(doc, I.session_attempt(r, None))
    p = root / I.answer_rel(family, eid, role)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(I.dumps(doc), encoding="utf-8")
    return p


def fill(root: Path, family: str = "same") -> None:
    """Every entry answered by both labellers: trigger untrusted quoting the title's first 12 characters."""
    for eid, t in I.texts(root).items():
        for r in I.ROLES:
            write_answer(root, family, eid, r, [reply(trigger=("untrusted", t[:12]))])


def collect_refused(root: Path, family: str = "same") -> str:
    """The refusal's text; fails when collect does not refuse."""
    try:
        I.collect(root, family)
    except I.Refused as e:
        return str(e)
    raise AssertionError("collect did not refuse")


# ---------------------------------------------------------------------------------------------- T1
class TestPins(unittest.TestCase):
    def test_instruments_pinned(self):  # T1
        inst = key()["thresholds"]["instruments"]
        self.assertEqual(sorted(inst), ["prompts/I54b_m5_truth_key.md", "spec/M5/lib/truth_labels.schema.json",
                                        "tests_m5/_i54b.py"])
        for p, h in sorted(inst.items()):
            self.assertEqual(file_sha256(ROOT / p), h, p)

    def test_inputs_match_the_pins(self):  # T1, R1
        self.assertEqual(I.check_inputs(ROOT), [])
        self.assertEqual(I.computed_pins(ROOT), key()["thresholds"]["pins"])
        self.assertEqual(key()["thresholds"]["pins"], I.pins(ROOT))

    def test_protocol_is_i54s(self):  # T1, R2
        i54 = load_json(ROOT / "spec/M5/preregistration.json")["instruments"]
        p = key()["thresholds"]["pins"]
        self.assertEqual(i54[I.PROTOCOL], p["protocol_sha256"])
        self.assertEqual(i54[I.PROMPT], p["prompt_sha256"])

    def test_key_counts(self):  # T1
        k = key()
        t = k["thresholds"]
        ids = sorted(e["id"] for e in load_json(ROOT / I.CORPUS)["entries"])
        self.assertEqual(len(ids), 20)
        self.assertEqual(sorted(t["pins"]["texts"]), ids)
        self.assertEqual(sorted(t["pins"]["packets"]), sorted(f"{i}.{r}" for i in ids for r in ("a", "b")))
        self.assertEqual(t["packets"]["count"], 40)
        self.assertEqual(t["labellers"]["per_entry"], 2)
        self.assertEqual(k["outcome_paths"], ["spec/M5/truth/", "docs/iterations/I54b.md"])
        self.assertEqual(sorted(PROTO["questions"]), list(I.QUESTIONS))
        self.assertEqual(PROTO["output"].split(":")[0], f"{I.TRUTH}/{I.OUTPUTS['same'][0]}")


# ---------------------------------------------------------------------------------------------- T2
LEAK_FIELDS = ("candidate", "fix_commit", "prefix_commit", "repo", "fix_date", "label")


def leak_strings(e: dict) -> list[str]:
    out = [e[k] for k in LEAK_FIELDS if isinstance(e.get(k), str)]
    out += list(e.get("files", []))
    out += [s["url"] for s in e.get("sources", [])]
    for lab in e.get("labels", {}).values():
        if isinstance(lab, dict):
            out += [v for v in (lab.get("justification"), lab.get("subform")) if isinstance(v, str) and v]
    return [s for s in out if len(s) >= 4]


class TestPackets(unittest.TestCase):
    def test_packets_committed(self):  # T2 (red until the packets are committed)
        with redirect_stdout(io.StringIO()) as out:
            rc = I.main(["packets", "--check"], ROOT)
        self.assertEqual(rc, 0, out.getvalue())
        idx = load_json(ROOT / I.PACKETS / "index.json")
        self.assertEqual(validate(idx, sch("packet_index")), [])
        self.assertEqual(len(idx["packets"]), 40)
        files = sorted(p.name for p in (ROOT / I.PACKETS).iterdir())
        self.assertEqual(len(files), 41)

    def test_packets_hold_only_the_text(self):  # T2
        tpl = (ROOT / I.PROMPT).read_text(encoding="utf-8")
        head, tail = tpl.split(I.SLOT)
        pk = I.packets(ROOT)
        for e in load_json(ROOT / I.CORPUS)["entries"]:
            t = I.entry_text(e)
            for r in I.ROLES:
                p = pk[f"{e['id']}.{r}"]
                self.assertTrue(p.startswith(head) and p.endswith(tail))
                self.assertEqual(p[len(head):len(p) - len(tail)], t)
                for s in leak_strings(e):
                    if s not in t and s not in tpl:
                        self.assertNotIn(s, p, f"{e['id']}: {s[:40]}")
                import re
                for tok in (rf"\b{e['id']}\b", r"HOLON", r"spec/", r"\bI4[0-9]\b", r"\bI5[0-9]b?\b"):
                    if not re.search(tok, t) and not re.search(tok, tpl):
                        self.assertIsNone(re.search(tok, p), f"{e['id']}: {tok}")

    def test_committed_packets_are_pinned_bytes(self):  # T2
        for n, h in sorted(I.pins(ROOT)["packets"].items()):
            self.assertEqual(file_sha256(ROOT / I.PACKETS / f"{n}.txt"), h, n)

    def test_render_refuses_a_bad_template(self):  # T2
        with self.assertRaises(I.Refused):
            I.render_packet("no slot", "x")
        with self.assertRaises(I.Refused):
            I.render_packet("{{TEXT}} {{TEXT}}", "x")
        self.assertEqual(I.render_packet("a {{TEXT}} b", "{{TEXT}}"), "a {{TEXT}} b")


# ---------------------------------------------------------------------------------------------- T3
VALUES = {q: PROTO["questions"][q]["values"] for q in I.QUESTIONS}


class TestRules(unittest.TestCase):
    T = "Title here\nA malicious   peer can\tcrash the node."

    def chk(self, q, v, quote):
        return I.check_answer(VALUES[q], {"value": v, "quote": quote}, self.T)

    def test_q1_value_outside_list(self):
        self.assertEqual(self.chk("trigger", "anyone", "A malicious"), ("undocumented", "Q1"))
        self.assertEqual(self.chk("trigger", "Untrusted", "A malicious"), ("undocumented", "Q1"))

    def test_q1_quote_with_undocumented(self):
        self.assertEqual(self.chk("trigger", "undocumented", "A malicious"), ("undocumented", "Q1"))
        self.assertEqual(self.chk("trigger", "undocumented", None), ("undocumented", None))

    def test_q2_not_a_substring(self):
        self.assertEqual(self.chk("trigger", "untrusted", "an attacker can crash"), ("undocumented", "Q2"))
        self.assertEqual(self.chk("trigger", "untrusted", "a malicious peer"), ("undocumented", "Q2"))  # case
        self.assertEqual(self.chk("trigger", "untrusted", "malicious peer can crash the node!"),
                         ("undocumented", "Q2"))

    def test_q2_null_quote_with_a_value(self):
        self.assertEqual(self.chk("actor_flow", "none", None), ("undocumented", "Q2"))

    def test_q2_whitespace_collapse(self):
        self.assertEqual(self.chk("trigger", "untrusted", "malicious peer can crash"), ("untrusted", None))
        self.assertEqual(self.chk("trigger", "untrusted", "here A malicious"), ("untrusted", None))  # across \n
        self.assertEqual(self.chk("trigger", "untrusted", "peer\n\ncan"), ("untrusted", None))
        self.assertEqual(self.chk("trigger", "untrusted", "peercan"), ("undocumented", "Q2"))  # no space invented

    def test_q2_empty_quote_is_a_substring(self):
        # The frozen Q2 is applied literally: the empty string is a substring of every text (Surprise, Question 2).
        self.assertEqual(self.chk("trigger", "untrusted", ""), ("untrusted", None))

    def test_q3(self):
        good = {q: {"value": v, "quote": None, "checked": v, "fails": None}
                for q, v in (("trigger", "untrusted"), ("actor_flow", "none"), ("doc_contradiction", "no"))}
        self.assertEqual(I.final(good, good), {"trigger": "untrusted", "actor_flow": "none",
                                               "doc_contradiction": "no"})
        other = json.loads(json.dumps(good))
        other["trigger"]["value"] = other["trigger"]["checked"] = "trusted_only"
        self.assertEqual(I.final(good, other)["trigger"], "undocumented")
        self.assertEqual(I.final(good, other)["actor_flow"], "none")
        failing = json.loads(json.dumps(good))
        failing["actor_flow"]["fails"] = "Q2"
        self.assertEqual(I.final(good, failing)["actor_flow"], "undocumented")
        self.assertEqual(I.final(failing, good)["actor_flow"], "undocumented")
        self.assertEqual(I.final(good, None), {q: "undocumented" for q in I.QUESTIONS})

    def test_derivations_exhaustive(self):
        l6 = {("untrusted", "gain"): "rational", ("untrusted", "none"): "rational",
              ("untrusted", "loss"): "irrational", ("untrusted", "undocumented"): "undocumented"}
        for t, a in itertools.product(VALUES["trigger"], VALUES["actor_flow"]):
            want = l6.get((t, a), "irrational" if t in ("trusted_only", "none") else "undocumented")
            self.assertEqual(I.derive_l6({"trigger": t, "actor_flow": a, "doc_contradiction": "no"}), want, (t, a))
        for d in VALUES["doc_contradiction"]:
            self.assertEqual(I.derive_l10({"trigger": "none", "actor_flow": "none", "doc_contradiction": d}), d)

    def test_shape(self):
        ok = json.loads(reply(trigger=("untrusted", "x")))
        self.assertTrue(I.answer_ok(ok))
        self.assertEqual(validate(ok, sch("answer_object")), [])
        bad = json.loads(reply())
        bad["extra"] = 1
        self.assertFalse(I.answer_ok(bad))
        bad = json.loads(reply())
        del bad["trigger"]
        self.assertFalse(I.answer_ok(bad))
        bad = json.loads(reply())
        bad["trigger"]["value"] = 3
        self.assertFalse(I.answer_ok(bad))
        bad = json.loads(reply())
        bad["trigger"]["why"] = "x"
        self.assertFalse(I.answer_ok(bad))
        self.assertTrue(I.answer_ok(json.loads(reply(trigger=("whoever", "x")))))  # Q1's job, not the shape's

    def test_parse(self):
        r = reply()
        self.assertEqual(I.session_outcome(r), "ok")
        self.assertEqual(I.session_outcome("```json\n" + r + "\n```\n"), "ok")
        self.assertEqual(I.session_outcome("Here it is:\n```json\n" + r + "\n```"), "unparsable")
        self.assertEqual(I.session_outcome("[1]"), "unparsable")
        self.assertEqual(I.session_outcome('{"trigger": 1}'), "invalid")
        self.assertEqual(I.session_outcome(None), "no_response")

    def test_cli_outcome(self):
        base = {"is_error": False, "num_turns": 1, "result": reply(), "session_id": "s", "subtype": "success"}
        self.assertEqual(I.cli_outcome(base), "ok")
        self.assertEqual(I.cli_outcome({**base, "is_error": True}), "cli_error")
        self.assertEqual(I.cli_outcome({**base, "is_error": None}), "cli_error")
        self.assertEqual(I.cli_outcome({**base, "num_turns": 2}), "turns")
        self.assertEqual(I.cli_outcome({**base, "num_turns": True}), "turns")
        self.assertEqual(I.cli_outcome({**base, "result": "no"}), "unparsable")

    def test_retry_rule(self):
        f = I.retry_follows
        self.assertTrue(f(["ok"]) and f(["invalid", "ok"]) and f(["invalid", "unparsable"]))
        self.assertTrue(f(["no_response", "invalid", "cli_error", "turns"]))
        self.assertTrue(f(["no_response"] * 5))
        self.assertFalse(f([]) or f(["ok", "ok"]) or f(["invalid"]) or f(["invalid", "turns", "ok"]))
        self.assertFalse(f(["no_response"] * 4) or f(["no_response"] * 6) or f(["weird"]))


# ---------------------------------------------------------------------------------------------- T4
class TestCollector(unittest.TestCase):
    def setUp(self):
        self.root = fixture_root()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_collect_is_deterministic_and_valid(self):
        fill(self.root)
        a = I.collect(self.root, "same")
        b = I.collect(self.root, "same")
        self.assertEqual(a, b)
        truth = json.loads(a[f"{I.TRUTH}/corpus.json"])
        self.assertEqual(validate(truth, sch("truth_file")), [])
        self.assertEqual(sorted(truth["entries"]), sorted(I.pins(self.root)["texts"]))
        e = truth["entries"]["c01"]
        self.assertEqual(e["final"], {"trigger": "untrusted", "actor_flow": "undocumented",
                                      "doc_contradiction": "undocumented"})
        self.assertEqual((e["l6"], e["l10"]), ("undocumented", "undocumented"))
        run = json.loads(a[f"{I.TRUTH}/corpus.run.json"])
        self.assertFalse(run["protocol_exact_invocation"])
        self.assertEqual(run["model_check"], "declared by the launcher, not observed")
        self.assertEqual(run["empty_quotes"], [])
        write_answer(self.root, "same", "c02", "a", [reply(trigger=("untrusted", " "))])
        run = json.loads(I.collect(self.root, "same")[f"{I.TRUTH}/corpus.run.json"])
        self.assertEqual(run["empty_quotes"], [{"entry": "c02", "question": "trigger", "role": "a"}])

    def test_disagreement_recorded_never_resolved(self):
        fill(self.root)
        t = text_of("c04")
        write_answer(self.root, "same", "c04", "a", [reply(trigger=("untrusted", t[:12]), actor=("none", t[:5]))])
        write_answer(self.root, "same", "c04", "b", [reply(trigger=("trusted_only", t[:12]), actor=("none", t[:5]))])
        out = I.collect(self.root, "same")
        e = json.loads(out[f"{I.TRUTH}/corpus.json"])["entries"]["c04"]
        self.assertEqual(e["final"]["trigger"], "undocumented")
        self.assertEqual(e["final"]["actor_flow"], "none")
        self.assertEqual(e["l6"], "undocumented")
        run = json.loads(out[f"{I.TRUTH}/corpus.run.json"])
        self.assertIn({"entry": "c04", "question": "trigger", "a": "untrusted", "b": "trusted_only"},
                      run["disagreements"])

    def test_a_paraphrased_quote_fails(self):
        fill(self.root)
        t = text_of("c04")
        for r in I.ROLES:
            write_answer(self.root, "same", "c04", r, [reply(trigger=("untrusted", "sent by an attacker node"),
                                                             actor=("none", t[:5]))])
        out = I.collect(self.root, "same")
        e = json.loads(out[f"{I.TRUTH}/corpus.json"])["entries"]["c04"]
        self.assertEqual((e["final"]["trigger"], e["final"]["actor_flow"]), ("undocumented", "none"))
        self.assertEqual(e["answers"]["a"]["trigger"]["fails"], "Q2")

    def test_rational_and_irrational(self):
        fill(self.root)
        t = text_of("c04")
        for r in I.ROLES:
            write_answer(self.root, "same", "c04", r, [reply(trigger=("untrusted", "attacker node"),
                                                             actor=("none", "p2p messages"), doc=("no", "DoS"))])
            write_answer(self.root, "same", "c05", r, [reply(trigger=("trusted_only", "privileged game configuration"))])
        es = json.loads(I.collect(self.root, "same")[f"{I.TRUTH}/corpus.json"])["entries"]
        self.assertEqual((es["c04"]["l6"], es["c04"]["l10"]), ("rational", "no"))
        self.assertEqual(es["c05"]["l6"], "irrational")
        self.assertIn("attacker node", t)

    def test_missing_and_stray_files_refused(self):
        fill(self.root)
        (self.root / I.answer_rel("same", "c07", "b")).unlink()
        self.assertIn("c07.b.json: missing", collect_refused(self.root))
        fill(self.root)
        (self.root / I.ANSWERS / "same" / "c21.a.json").write_text("{}", encoding="utf-8")
        self.assertIn("not an answer file", collect_refused(self.root))

    def tamper(self, eid, role, fn):
        p = self.root / I.answer_rel("same", eid, role)
        d = json.loads(p.read_text(encoding="utf-8"))
        fn(d)
        p.write_text(I.dumps(d), encoding="utf-8")

    def test_pin_and_path_tampering_refused(self):
        cases = [
            ("packet_sha256", lambda d: d.__setitem__("packet_sha256", "0" * 64)),
            ("do not match the path", lambda d: d.__setitem__("entry", "c02")),
            ("model_tag", lambda d: d.__setitem__("model_tag", "A")),
            ("invocation external", lambda d: d.__setitem__("invocation", "external")),
            ("recomputes", lambda d: d["attempts"][0].__setitem__("outcome", "invalid")),
            ("answer is not", lambda d: d["answer"]["trigger"].__setitem__("value", "trusted_only")),
            ("$", lambda d: d.__setitem__("labels", "x")),
            ("retry rule", lambda d: d["attempts"].append(dict(d["attempts"][0]))),
            ("packet", lambda d: d.__setitem__("packet", "spec/M5/truth/packets/c02.a.txt")),
        ]
        for want, fn in cases:
            fill(self.root)
            self.tamper("c03", "b", fn)
            self.assertIn(want, collect_refused(self.root), want)

    def test_packet_bytes_and_inputs_refused(self):
        fill(self.root)
        p = self.root / I.packet_rel("c09", "a")
        p.write_text(p.read_text(encoding="utf-8") + "The fix is in handler.go.\n", encoding="utf-8")
        self.assertIn("does not hash to the pin", collect_refused(self.root))
        I.write_files(self.root, I.packet_files(self.root), False, I.PACKETS)
        c = self.root / I.CORPUS
        c.write_text(c.read_text(encoding="utf-8").replace("attacker node", "attacker"), encoding="utf-8")
        self.assertIn("corpus_sha256", collect_refused(self.root))
        with self.assertRaises(I.Refused):
            I.packet_files(self.root)

    def test_prompt_change_refused(self):
        fill(self.root)
        p = self.root / I.PROMPT
        p.write_text(p.read_text(encoding="utf-8").replace("alone", "and the repository"), encoding="utf-8")
        self.assertIn("prompt_sha256", collect_refused(self.root))

    def test_answer_command_and_retry(self):
        resp = self.root / "resp.txt"
        resp.write_text("I think trigger is untrusted.", encoding="utf-8")
        args = ["answer", "--root", str(self.root), "--family", "same", "--invocation", "cloud_session",
                "--entry", "c01", "--role", "a"]
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            self.assertEqual(I.main(args + ["--response-file", str(resp), "--session", "s1"]), 0)
            self.assertIn("needs another fresh session", out.getvalue())
            self.assertEqual(I.main(args + ["--no-response"]), 0)
            resp.write_text("```json\n" + reply() + "\n```\n", encoding="utf-8")
            self.assertEqual(I.main(args + ["--response-file", str(resp)]), 0)
            self.assertIn("finished", out.getvalue())
            self.assertEqual(I.main(args + ["--response-file", str(resp)]), 1)   # nothing after ok
            self.assertEqual(I.main(args[:6] + ["external", "--entry", "c01", "--role", "a", "--no-response"]), 1)
        d = load_json(self.root / I.answer_rel("same", "c01", "a"))
        self.assertEqual([a["outcome"] for a in d["attempts"]], ["unparsable", "no_response", "ok"])
        self.assertEqual(d["answer"], json.loads(reply()))
        self.assertEqual(validate(d, sch("answer_file")), [])

    def test_two_counted_failures_give_no_answer(self):
        fill(self.root)
        write_answer(self.root, "same", "c10", "a", ["nope", "still nope"])
        es = json.loads(I.collect(self.root, "same")[f"{I.TRUTH}/corpus.json"])["entries"]
        self.assertIsNone(es["c10"]["answers"]["a"])
        self.assertEqual(es["c10"]["final"], {q: "undocumented" for q in I.QUESTIONS})

    def test_families_never_pooled(self):
        fill(self.root)
        fill(self.root, "different")
        t = text_of("c04")
        for r in I.ROLES:
            write_answer(self.root, "different", "c04", r, [reply(trigger=("trusted_only", t[:12]))])
        I.write_files(self.root, I.collect(self.root, "same"), False)
        I.write_files(self.root, I.collect(self.root, "different"), False)
        cmp_ = json.loads(I.compare(self.root)[f"{I.TRUTH}/family_comparison.json"])
        self.assertFalse(cmp_["pooled"])
        self.assertEqual(cmp_["counts"]["trigger"], {"equal": 19, "differ": 1})
        same = load_json(self.root / I.TRUTH / "corpus.json")
        self.assertEqual(same["entries"]["c04"]["final"]["trigger"], "untrusted")
        with self.assertRaises(I.Refused):   # a cloud_session answer is not a different-family answer
            I.new_answer_file(self.root, "different", "cloud_session", "c01", "a")

    def test_frozen_invocation_runner(self):
        store = self.root / "store.json"
        calls = []

        def fake(model, result="", turns=1, err=False, models=None):
            return json.dumps({"is_error": err, "num_turns": turns, "result": result, "session_id": "x",
                               "subtype": "success", "modelUsage": {m: {} for m in (models or [model])}})

        script = {"A": [fake("mA", "garbage"), fake("mA", reply())], "B": [None, fake("mB", reply())]}

        def run_cli(argv, prompt, env, cwd, timeout):
            m = argv[argv.index("--model") + 1]
            calls.append((argv, prompt, cwd, timeout))
            self.assertTrue(Path(cwd).is_dir() and not any(Path(cwd).iterdir()))
            return script["A" if m == "mA" else "B"].pop(0)

        slept = []
        old = (I.run_cli, I.sleep)
        I.run_cli, I.sleep = run_cli, slept.append
        try:
            I.run(self.root, "a", "mA", ["c01"], store)
            I.run(self.root, "b", "mB", ["c01"], store)
            inv = I.invocation(self.root)
            self.assertEqual(calls[0][0][:4], ["claude", "-p", "--tools", ""])
            self.assertEqual(calls[0][1], (self.root / I.packet_rel("c01", "a")).read_text(encoding="utf-8"))
            self.assertEqual(calls[0][3], inv["timeout_seconds"])
            self.assertEqual(slept, [I.RETRY_WAIT])
            d = load_json(self.root / I.answer_rel("same", "c01", "a"))
            self.assertEqual([a["outcome"] for a in d["attempts"]], ["unparsable", "ok"])
            self.assertEqual(d["invocation"], "cli")
            self.assertNotIn("mA", json.dumps(d))
            # a_differs_from_b and one_model_per_role
            script["A"] = [fake("mA", reply())]
            with self.assertRaises(I.Refused):
                I.run(self.root, "b", "mA", ["c02"], store)
            script["A"] = [fake("mA", reply(), models=["mA", "mC"])]
            with self.assertRaises(I.Refused):
                I.run(self.root, "a", "mA", ["c03"], store)
        finally:
            I.run_cli, I.sleep = old


# ---------------------------------------------------------------------------------------------- T5
def truth() -> dict:
    return load_json(ROOT / I.TRUTH / "corpus.json")


def run_sidecar() -> dict:
    return load_json(ROOT / I.TRUTH / "corpus.run.json")


class TestTruth(unittest.TestCase):
    def test_truth_committed(self):  # T5 (red until labelled)
        files = I.collect(ROOT, "same")
        for rel, text in files.items():
            self.assertEqual((ROOT / rel).read_text(encoding="utf-8"), text, rel)
        t = truth()
        self.assertEqual(validate(t, sch("truth_file")), [])
        self.assertEqual((t["protocol_sha256"], t["corpus_sha256"]),
                         (I.pins(ROOT)["protocol_sha256"], I.pins(ROOT)["corpus_sha256"]))

    def test_answers_land_in_one_commit(self):  # T5: no labeller can read another's committed answer
        for fam in I.FAMILIES:
            out = git("log", "--diff-filter=A", "--format=%H", "--", f"{I.ANSWERS}/{fam}/").decode().split()
            if fam == "same":
                self.assertEqual(len(out), 1, "the same-family answers are added in exactly one commit")
            else:
                self.assertLessEqual(len(out), 1, "the different-family answers are added in at most one commit")
            if out:
                added = git("show", "--diff-filter=A", "--name-only", "--format=", out[0], "--",
                            f"{I.ANSWERS}/{fam}/").decode().split()
                self.assertEqual(len(added), 40, fam)

    def test_different_family_beside_never_pooled(self):  # T5
        diff = ROOT / I.ANSWERS / "different"
        cd, cmp_ = ROOT / I.TRUTH / "corpus_different.json", ROOT / I.TRUTH / I.COMPARISON
        if not diff.exists():
            self.assertFalse(cd.exists() or cmp_.exists())
            return
        for rel, text in {**I.collect(ROOT, "different"), **I.compare(ROOT)}.items():
            self.assertEqual((ROOT / rel).read_text(encoding="utf-8"), text, rel)


# ---------------------------------------------------------------------------------------------- T6
PROTECTED = ["results/M0", "results/M1", "results/M2", "results/M3", "results/M4", "gen/M0", "gen/M1", "gen/M2",
             "gen/M3", "gen/M4", "laws", "replay", "spec/M0", "spec/M1", "spec/M2", "spec/M3", "spec/M4", "spec/eval",
             "spec/heldout", "facts", "predictions", "schemas", "tests", "bend/probes", "docs/M0_SPEC.md",
             "docs/BEND_PRIMER.md", "AGENTS.md", "tools/freeze.py", "FROZEN.sha256", "spec/M5/lib/truth_protocol.json",
             "spec/M5/lib/truth_prompt.md", "spec/M5/lib/environment_classes.json", "spec/M5/lib/inputs.schema.json",
             "spec/M5/predictions/I54.json", "spec/M5/controls", "tests_m5/_i54.py", "tests_m5/_m5.py",
             "tests_m5/test_m5_definitions.py", "tests_m5/__init__.py"]


I54B_PATHS = ["prompts/I54b_m5_truth_key.md", "spec/M5/predictions/I54b.json", "spec/M5/lib/truth_labels.schema.json",
              "spec/M5/truth", "tests_m5/_i54b.py", "tests_m5/test_m5_truth_key.py", "docs/iterations/I54b.md",
              "spec/M5/amendments/I54b.jsonl"]


class TestScope(unittest.TestCase):
    def test_only_i54b_paths_change(self):  # T6, R3 (amended: spec/M5/amendments/I54b.jsonl)
        """I54b's own commits (the non-merge commits after the base that touch one of I54b's paths) change no
        protected path. A merge of the trunk into the branch brings other iterations' changes, which are not I54b's."""
        base = key()["thresholds"]["base_commit"]
        own = git("log", "--no-merges", "--format=%H", f"{base}..HEAD", "--", *I54B_PATHS).decode().split()
        self.assertTrue(own, "no I54b commit found after the base")
        for c in own:
            out = git("diff-tree", "--no-commit-id", "--name-only", "-r", c, "--", *PROTECTED).decode()
            self.assertEqual([p for p in out.split("\n") if p], [], c)


# ---------------------------------------------------------------------------------------------- P1-P5
def decided6(t: dict) -> list[str]:
    return [i for i, e in sorted(t["entries"].items()) if i != "c13" and e["l6"] in ("rational", "irrational")]


class TestPredictions(unittest.TestCase):
    def pred(self, pid):
        return next(p for p in key()["predictions"] if p["id"] == pid)["expected"]

    def test_p1_l6_decided(self):
        self.assertGreaterEqual(len(decided6(truth())), self.pred("I54b-P1"))

    def test_p2_l6_irrational(self):
        n = sum(1 for i, e in truth()["entries"].items() if i != "c13" and e["l6"] == "irrational")
        self.assertLessEqual(n, self.pred("I54b-P2"))

    def test_p3_l10_yes(self):
        lo, hi = self.pred("I54b-P3")
        n = sum(1 for e in truth()["entries"].values() if e["l10"] == "yes")
        self.assertTrue(lo <= n <= hi, n)

    def test_p4_trigger_agreement(self):
        t = truth()
        n = sum(1 for e in t["entries"].values() if e["answers"]["a"] is not None and e["answers"]["b"] is not None
                and e["answers"]["a"]["trigger"]["value"] == e["answers"]["b"]["trigger"]["value"])
        self.assertGreaterEqual(n, self.pred("I54b-P4"))

    def test_p5_q2_failures(self):
        n = sum(1 for f in run_sidecar()["rule_failures"] if f["rule"] == "Q2")
        self.assertLessEqual(n, self.pred("I54b-P5"))


if __name__ == "__main__":
    unittest.main()
