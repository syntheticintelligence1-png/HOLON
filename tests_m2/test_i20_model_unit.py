"""I20 builder A (model side), unit tests on planted toys: not preregistered, not an outcome. The contract is the
docstring of tests_m2/test_extracted_refinement.py; these tests check holon.machine (loading, programs, check ids),
holon.extracted_eval (the A/B interface step), holon.machine_bend (the Bend model and its agreement with the
evaluator), holon.window (classification, view, window_check) and holon.differential (mechanical deltas, the window
view of the abstraction, ghost reads) on tests_m2/fixtures/i20_model/toy/.

The toy is src/Book.sol. book.extracted.json is its I19 extraction (the current shape); book.a19.json adds, by hand,
the sections of the planned I19 follow-up shape (writes, panics, calls, dispatcher checks, events, loop records,
inherited storage). The expected storage words, logs and revert data below were observed on the real contract (forge,
the pinned solc) from the same pre-state, so the evaluator is checked against the code, not against itself.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, load_json, run_holon

TOY = ROOT / "tests_m2" / "fixtures" / "i20_model" / "toy"
OWNER = 0xA11CE
GATE = 0xBEEF
S = "src/Book.sol"


def h32(v: int) -> str:
    return "0x%064x" % v


def pre_state() -> dict:
    """slot 0: _owner | _stopped (offset 20) | total = 5 (offset 21); slot 1: gate; slot 2: count = 7."""
    return {h32(0): h32(OWNER | (5 << 168)), h32(1): h32(GATE), h32(2): h32(7)}


def env(caller=OWNER, value=0, allowed=(True, 1)) -> dict:
    ok, ret = allowed
    return {"caller": caller, "this": 0x1234, "msg.value": value, "block.timestamp": 100,
            "calls": [{"fn": "IGate.allowed", "to": "0x%040x" % GATE, "args": {"who": "0x%040x" % caller},
                       "ok": ok, "ret": h32(ret) if isinstance(ret, int) else ret}]}


def build_dir() -> str:
    d = os.environ.get("HOLON_BUILD_DIR")
    return d if d else str(ROOT / "build")


class _Toy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from holon import machine
        cls.machine = machine
        cls.a19 = machine.load_extracted(TOY / "book.a19.json", ROOT, source=TOY)
        cls.i19 = machine.load_extracted(TOY / "book.extracted.json", ROOT, source=TOY)

    def step(self, m, action, args, e=None, state=None):
        from holon import extracted_eval as X
        return X.step(m, state or pre_state(), action, args, e or env())


class TestModel(_Toy):
    def test_families_include_the_inherited_storage_at_the_compilers_slots(self):
        f = self.a19.families
        self.assertEqual((f["_owner"].slot, f["_owner"].offset, f["_owner"].declared), (0, 0, False))
        self.assertEqual((f["_stopped"].slot, f["_stopped"].offset), (0, 20))
        self.assertEqual((f["total"].slot, f["total"].offset, f["total"].declared), (0, 21, True))
        self.assertEqual(sorted(self.i19.families), sorted(f))   # the I19 shape resolves them from the layout

    def test_check_ids_and_program_order(self):
        ids = [c.id for c in self.a19.reaches("deposit")]
        self.assertEqual(ids, ["deposit#abi#0", f"deposit#{S}:21#0", f"deposit#{S}:47#0", f"deposit#{S}:48#0",
                               f"deposit#{S}:48#1", f"deposit#{S}:49#0", f"deposit#{S}:50#0"])
        self.assertEqual([c.id for c in self.a19.reaches("share")],
                         ["share#callvalue#0", f"share#{S}:69#0", f"share#{S}:69#1", f"share#{S}:69#2"])
        # the loop body's checks are checks of the action, in walk order
        self.assertEqual([c.id for c in self.a19.reaches("seal")],
                         ["seal#callvalue#0", f"seal#{S}:16#0", f"seal#{S}:75#0", f"seal#{S}:74#0",
                          f"seal#{S}:77#0"])
        self.assertEqual([c.id for c in self.i19.reaches("deposit")],
                         [f"deposit#{S}:21#0", f"deposit#{S}:47#0", f"deposit#{S}:48#0"])

    def test_shapes(self):
        self.assertEqual({a: self.a19.program(a).shape for a in self.a19.actions}, dict.fromkeys(self.a19.actions, "a19"))
        self.assertEqual(self.a19.program("deposit").missing, [])
        self.assertEqual(self.i19.program("deposit").missing, ["writes", "events"])

    def test_a_family_off_the_compilers_layout_is_refused(self):
        doc = load_json(TOY / "book.a19.json")
        doc["storage"][0]["offset"] = 0
        with self.assertRaises(self.machine.ModelError):
            self.machine.ExtractedModel(doc, self.a19.info)

    def test_a_record_without_seq_is_refused_in_the_a19_shape(self):
        doc = load_json(TOY / "book.a19.json")
        a = next(x for x in doc["actions"] if x["name"] == "deposit")
        del a["writes"][0]["seq"]
        with self.assertRaises(self.machine.ModelError):
            self.machine.ExtractedModel(doc, self.a19.info)

    def test_an_order_list_places_records_without_seq(self):
        """The follow-up's minimum (A19-03): an "order" list over the checks instead of seq on every record."""
        doc = load_json(TOY / "book.a19.json")
        a = next(x for x in doc["actions"] if x["name"] == "deposit")
        for sec in ("checks", "panics", "calls", "writes", "events"):
            for r in a.get(sec) or []:
                r.pop("seq", None)
        for g in a["guards"]:
            for r in g.get("reaches") or []:
                r.pop("seq", None)
        a["order"] = [["check", 0], ["guard", f"{S}:21", 0], ["guard", f"{S}:47", 0], ["call", 0],
                      ["guard", f"{S}:48", 0], ["panic", 0], ["panic", 1]]
        m = self.machine.ExtractedModel(doc, self.a19.info)
        self.assertEqual([c.id for c in m.reaches("deposit")], [c.id for c in self.a19.reaches("deposit")])
        from holon import extracted_eval as X
        for args in ({"amount": 3}, {"amount": 0}):
            self.assertEqual(X.step(m, pre_state(), "deposit", args, env()),
                             X.step(self.a19, pre_state(), "deposit", args, env()))

    def test_loop_bodies_given_as_lists_are_classified(self):
        doc = load_json(TOY / "book.a19.json")
        lp = next(x for x in doc["actions"] if x["name"] == "seal")["loops"][0]
        lp["steps"] = [dict(p, type="panic") for p in lp["steps"]["panics"]]
        m = self.machine.ExtractedModel(doc, self.a19.info)
        self.assertEqual([c.id for c in m.reaches("seal")], [c.id for c in self.a19.reaches("seal")])


class TestEvaluator(_Toy):
    """The observations of the real contract (forge, the pinned solc) from pre_state()."""

    def test_deposit_ok_writes_packed_slots_a_struct_and_an_event(self):
        r = self.step(self.a19, "deposit", {"amount": 3})
        self.assertEqual(r["status"], "ok", r)
        from holon.keccak import keccak256
        e8 = "0x" + keccak256((8).to_bytes(32, "big") + (3).to_bytes(32, "big")).hex()
        self.assertEqual(r["writes"], {
            h32(0): "0x00000000000000000000080000000000000000000000000000000000000a11ce",
            h32(2): h32(8),
            e8: "0x0000000800000000000000000000000000000000000a11ce0000000000000003"})
        self.assertEqual(r["events"], [{"topics": ["0xcd50943caf3a035e3821448b2743faef90aae73ff20c6c1b29ea8213ad1fee1d",
                                                   h32(OWNER), h32(8)], "data": h32(3)}])
        self.assertIsNone(r["guard"])

    def test_guard_reverts_carry_the_reason_and_the_check_id(self):
        r = self.step(self.a19, "deposit", {"amount": 0})
        self.assertEqual((r["status"], r["guard"]), ("revert", f"deposit#{S}:47#0"))
        self.assertEqual(r["revert"], "0x08c379a0" + h32(32)[2:] + h32(4)[2:] + b"zero".hex() + "00" * 28)
        r = self.step(self.a19, "setStopped", {"on": True}, env(caller=0xB0B))
        self.assertEqual(r["guard"], f"setStopped#{S}:16#0")

    def test_custom_error_without_recorded_arguments_gives_its_selector_as_a_prefix(self):
        r = self.step(self.a19, "withdraw", {"id": 8})
        self.assertEqual((r["status"], r["revert"], r.get("revert_prefix")), ("revert", "0x3715f556", True))
        self.assertEqual(r["guard"], f"withdraw#{S}:57#0")
        # with the error's arguments recorded (a possible follow-up key), the whole data: forge saw 0x3715f556 || 8
        doc = load_json(TOY / "book.a19.json")
        g = next(x for x in doc["actions"] if x["name"] == "withdraw")["guards"][1]
        g["args"] = [["param", "id"]]
        m = self.machine.ExtractedModel(doc, self.a19.info)
        self.assertEqual(self.step(m, "withdraw", {"id": 8})["revert"], "0x3715f556" + h32(8)[2:])

    def test_panics_dispatcher_checks_and_bubbled_calls(self):
        r = self.step(self.a19, "share", {"a": 9, "b": 0})
        self.assertEqual((r["revert"], r["guard"]), ("0x4e487b71" + h32(0x12)[2:], f"share#{S}:69#0"))
        self.assertEqual(self.step(self.a19, "share", {"a": 9, "b": 2})["status"], "ok")
        st = pre_state()
        st[h32(0)] = h32(OWNER | (((1 << 64) - 1) << 168))
        r = self.step(self.a19, "deposit", {"amount": 1}, state=st)
        self.assertEqual((r["revert"], r["guard"]), ("0x4e487b71" + h32(0x11)[2:], f"deposit#{S}:49#0"))
        r = self.step(self.a19, "withdraw", {"id": 8}, env(value=1))
        self.assertEqual((r["status"], r["revert"], r["guard"]), ("revert", "0x", "withdraw#callvalue#0"))
        r = self.step(self.a19, "deposit", {"amount": 1 << 64})
        self.assertEqual((r["revert"], r["guard"]), ("0x", "deposit#abi#0"))
        r = self.step(self.a19, "deposit", {"amount": 1}, env(allowed=(False, "0xdeadbeef")))
        self.assertEqual((r["status"], r["revert"], r["guard"]), ("revert", "0xdeadbeef", f"deposit#{S}:48#0"))

    def test_loops_run_their_carried_values(self):
        self.assertEqual(self.step(self.a19, "seal", {"n": 0})["revert"], "0x3db2a12a")
        r = self.step(self.a19, "seal", {"n": 5})
        self.assertEqual(r["writes"], {h32(4): "0x3ed157e83ab1bb1f6b7b3760b3368106283d4e15d1f1b08e20d06576445a9994"})

    def test_memory_regions_hash_their_writes(self):
        r = self.step(self.a19, "stamp", {"idx": 5})
        self.assertEqual(r["writes"], {h32(4): "0xfe07a98784cd1850eae35ede546d7028e6bf9569108995fc410868db775e5e6a"})

    def test_setstopped_writes_the_inherited_bool_in_the_packed_slot(self):
        r = self.step(self.a19, "setStopped", {"on": True})
        self.assertEqual(r["writes"], {h32(0): "0x00000000000000000000050100000000000000000000000000000000000a11ce"})
        self.assertEqual(r["events"], [{"topics": ["0x593eae32baa13087e4ace6c5bdb2bca644d29310634cb44a78f0f2a640c6af0e"],
                                        "data": h32(1)}])

    def test_unsupported_never_guesses(self):
        e = env()
        del e["calls"]
        r = self.step(self.a19, "deposit", {"amount": 3}, e)
        self.assertEqual(r["status"], "unsupported")
        self.assertIn("external calls", r["reason"])
        # the I19 shape decides reverts, and says it cannot give an ok step's writes and events
        self.assertEqual(self.step(self.i19, "deposit", {"amount": 0})["guard"], f"deposit#{S}:47#0")
        r = self.step(self.i19, "deposit", {"amount": 3})
        self.assertEqual(r["status"], "unsupported")
        self.assertEqual(r["partial"]["unknown"], ["writes", "events"])


class TestBendModel(_Toy):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from holon import bend
        from holon.machine_bend import BendModel
        cls.bend = bend
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i20a-"))
        cls.gen = {}
        for name, m in (("a19", cls.a19), ("i19", cls.i19)):
            g = BendModel(m)
            text = g.generate()
            p = cls.tmp / name / "model.bend"
            p.parent.mkdir(parents=True)
            p.write_text(text)
            cls.gen[name] = (g, p, text)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_models_check_without_escape_hatches(self):
        for name, (_g, p, text) in sorted(self.gen.items()):
            with self.subTest(model=name):
                self.assertEqual(self.bend.escape_hatches(text), [])
                r = self.bend.check(p, self.bend.config(ROOT))
                self.assertTrue(r.ok, r.out[-2000:])

    def test_chk_and_step_agree_with_the_evaluator(self):
        g, p, _ = self.gen["a19"]
        art = p.with_suffix(".mjs")
        r = self.bend.run([p.name, "-o", art.name], cwd=p.parent, cfg=self.bend.config(ROOT))
        self.assertEqual(r.code, 0, r.out[-2000:])
        fields = {f: (0 if ty == "Nat" else []) for f, ty, _ in g.store_fields}
        fields.update({"f__owner": OWNER, "f__stopped": 0, "f_total": 5, "f_gate": GATE, "f_count": 7})

        def henv(caller, ok):
            e = {"$": "HEnv", "blobs": [], "kec": [], "sha": [], "unk": []}
            for k in g.env_keys:
                e["e_" + k.replace(".", "_")] = {"caller": caller, "msg.value": 0, "this": 0x1234}.get(k, 0)
            for i, fn in enumerate(g.calls):
                e[f"c{i}"] = [{"$": "HKL", "b": [caller], "v": [1 if ok else 0, 1]}] if fn == "IGate.allowed" else []
            return e

        cases = [("deposit", {"amount": 3}, OWNER, True, 0), ("deposit", {"amount": 0}, OWNER, True, None),
                 ("deposit", {"amount": 3}, OWNER, False, None), ("setStopped", {"on": 1}, 0xB0B, True, None),
                 ("setStopped", {"on": 1}, OWNER, True, None), ("share", {"a": 9, "b": 0}, OWNER, True, None)]
        calls = []
        for act, args, caller, ok, _ in cases:
            ar = {"$": f"A_{act}", **args}
            st = {"$": "HStore", **fields}
            calls.append({"fn": f"chk_{act}", "args": [st, ar, henv(caller, ok)]})
        calls.append({"fn": "step_deposit", "args": [{"$": "HStore", **fields}, {"$": "A_deposit", "amount": 3},
                                                     henv(OWNER, True)]})
        req = {"module": str(art), "calls": calls}
        out = subprocess.run(["node", str(ROOT / "holon" / "js" / "machine.mjs")], input=json.dumps(req),
                             capture_output=True, text=True, timeout=300)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        res = json.loads(out.stdout)["results"]
        for (act, args, caller, ok, _), got in zip(cases, res):
            with self.subTest(action=act, args=args, caller=caller, ok=ok):
                e = env(caller=caller, allowed=(ok, 1 if ok else "0x"))
                r = self.step(self.a19, act, {k: bool(v) if act == "setStopped" else v for k, v in args.items()}, e)
                ids = [c.id for c in self.a19.reaches(act)]
                want = 0 if r["status"] == "ok" else ids.index(r["guard"]) + 1
                self.assertEqual(got, want, (r, got))
        post = res[-1]
        self.assertEqual((post["f_total"], post["f_count"]), (8, 8))
        self.assertEqual(post["f_entries"], [{"$": "HKS_HBook_Entry", "k": 8,
                                              "v": {"$": "HBook_Entry", "amount": 3, "who": OWNER, "tag": 8}}])


class TestWindowAndDifferential(_Toy):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from holon import differential as D
        from holon import window as W
        cls.W, cls.D = W, D
        cls.decl = load_json(TOY / "window_book.json")
        cls.facts = load_json(TOY / "book_abstraction.json")

    def test_classification(self):
        cls = self.W.classify(self.a19, self.decl, self.facts)
        kinds = {(x.get("record"), x["field"]): x["kind"] for x in cls["fields"]}
        self.assertEqual(kinds[(None, "marks")], "ghost")
        self.assertEqual(kinds[("E", "mark")], "ghost")
        self.assertEqual(kinds[(None, "allowed")], "external")
        self.assertEqual(kinds[(None, "t")], "state_unmapped")
        self.assertEqual(kinds[(None, "log")], "state_unmapped")
        self.assertEqual(kinds[(None, "total")], "mapped")
        self.assertEqual(kinds[("E", "amount")], "mapped")
        self.assertEqual(cls["families"]["unmapped"], ["gate", "last"])

    def test_a_declaration_that_maps_a_ghost_field_is_refused(self):
        d = json.loads(json.dumps(self.decl))
        d["fields"]["marks"] = {"term": ["storage", "count"]}
        with self.assertRaises(self.W.WindowError):
            self.W.classify(self.a19, d, self.facts)

    def test_view_and_window_check(self):
        st = load_json(TOY / "window_states.json")["states"][0]["raw"]
        vw = self.W.view(self.a19, self.decl, st)
        self.assertEqual(vw["total"], 5)
        self.assertEqual(vw["owner"], OWNER)
        self.assertEqual(vw["entries"], [{"amount": 5, "who": 0xB0B}])
        out = self.W.check(self.a19, self.decl, ROOT)
        self.assertEqual(out["states"], 2)
        self.assertEqual(sorted((d["state"], d["field"], d["window"], d["abstraction"]) for d in out["disagreements"]),
                         [("t0:2", "stopped", 0, 1), ("t0:2", "total", 5, 6)])

    def test_deltas_are_mechanical(self):
        ab = self.D.Abstraction(self.facts, {})
        ds = {d["id"]: d for d in self.D.compute_deltas(self.a19, self.decl, self.facts, ab)}
        missing = sorted(i for i, d in ds.items() if d["kind"] == "guard_missing")
        self.assertEqual(missing, ["guard_missing:deposit:oracle: IGate.allowed"])
        extra = sorted(i for i, d in ds.items() if d["kind"] == "guard_extra")
        # the dispatcher's checks (no span) and the action's own checks without an abstraction require; the checked
        # add at :49 is matched by the abstraction's require at :49
        self.assertIn("guard_extra:deposit#abi#0", extra)
        self.assertIn(f"guard_extra:deposit#{S}:48#0", extra)
        self.assertNotIn(f"guard_extra:deposit#{S}:49#0", extra)
        self.assertEqual(sorted(i for i, d in ds.items() if d["kind"] == "ghost"), ["ghost:E.mark", "ghost:marks"])
        self.assertIn("mark_of", ds["ghost:E.mark"]["names"])
        self.assertEqual(sorted(i for i, d in ds.items() if d["kind"] == "family_unmapped"),
                         ["family_unmapped:gate", "family_unmapped:last"])
        view = self.D.view_facts(self.facts, list(ds.values()), "toy.json", "0" * 64, None)
        dep = next(a for a in view["actions"] if a["name"] == "deposit")
        self.assertEqual([g["src"] for g in dep["guards"]], [f"{S}:21", f"{S}:47", f"{S}:49"])

    def test_ghost_reads_and_cone_names(self):
        ab = self.D.Abstraction(self.facts, {})
        readers = ab.ghost_readers()
        self.assertEqual(sorted(readers), ["first_mark", "mark_of"])
        law = {"law_id": "L_x", "statement": {"claim": {"eq": [{"obsv": "first_mark", "of": {"s0": {}}}, {"nat": 0}]}}}
        self.assertIsNotNone(self.D.ghost_reason(law, ab, readers))
        law2 = {"law_id": "L_y", "statement": {"claim": {"eq": [{"obsv": "sum", "of": {"s0": {}}}, {"nat": 0}]}}}
        self.assertIsNone(self.D.ghost_reason(law2, ab, readers))
        self.assertTrue(ab.shares(["deposit"], ["dec_deposit_3"]))
        self.assertTrue(ab.shares(["E.mark"], ["g_E_mark"]))
        self.assertTrue(ab.shares(["mark_of"], ["d_mark_of"]))
        self.assertFalse(ab.shares(["total"], ["g_E_amount", "exec_deposit"]))


class TestModelCLI(unittest.TestCase):
    def test_holon_model_writes_a_checked_model_twice_the_same(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i20a-"))
        try:
            outs = []
            for k in range(2):
                p = run_holon(["model", "--facts", "tests_m2/fixtures/i20_model/toy/book.a19.json", "--out",
                               str(tmp / str(k)), "--source", str(TOY)], timeout=600)
                self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
                self.assertIn("ALL PROOFS CHECK", p.stdout)
                outs.append({f: (tmp / str(k) / f).read_bytes() for f in ("model.bend", "layout.json")})
            self.assertEqual(outs[0], outs[1])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
