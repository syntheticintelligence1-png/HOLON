"""F38 (lead ruling Q39, not preregistered): G2 verifies claimed signatures itself, against keys the human froze; each
gate re-runs only its own milestone's binding_change proofs; the checker runs with a registered stack, set in its own
process only.

  signatures  a signature counts only against a frozen key (statement_diff.frozen_keys): keys/<name> under the freeze
              in tools/freeze.py and listed in FROZEN.sha256 with its sha256, and, for a committed line, frozen with the
              same bytes at the commit that appended it. A committed line that carries a signature, or whose acceptance
              record claims one, is verified by G2; with no frozen key it fails (never taken on trust), and a
              binding_change's equivalence is skipped only for a signature that verifies.
  scope       on git, a committed binding_change line of a law of another milestone than the gated one gets every check
              (its artifacts regenerated and tied to its two models and statement) but the kernels' runs on its proof,
              which its own milestone's G2 makes (listed in "elsewhere").
  stack       the checker's environment carries no inherited BUN_JSC_* option and the registered JavaScript stack
              (config/holon.json bend.js_stack_mb); a launcher sets RLIMIT_STACK in the checker's process, never in this
              one; a proof of a 20000-deep term, which overflows a 4 MB stack (bun's default is about 5 MB), gets a
              verdict from both kernels, both ways (a true law accepted, a false one rejected).
"""
from __future__ import annotations

import hashlib
import json
import os
import resource
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests_m3._m3 import ROOT  # noqa: F401  (puts the repository on sys.path)

from holon import bend
from holon import statement_diff as SD


def head() -> str:
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


SIG = "-----BEGIN PGP SIGNATURE-----\n\nAAAA\n-----END PGP SIGNATURE-----\n"
LAW = {"law_id": "L_x", "statement": {"claim": "x"}}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Gpg:
    """A throwaway signing key (the human's stand-in) in its own GNUPGHOME."""

    def __init__(self, uid: str):
        self.home = Path(tempfile.mkdtemp(prefix="f38-gpg-"))
        os.chmod(self.home, 0o700)
        self.env = {"GNUPGHOME": str(self.home), "PATH": os.environ.get("PATH", ""), "LC_ALL": "C"}
        self.gpg(["--quick-gen-key", uid, "ed25519", "sign", "never"])
        self.public = self.gpg(["--armor", "--export"]).stdout

    def gpg(self, args, data: bytes | None = None):
        r = subprocess.run(["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", "", *args],
                           env=self.env, input=data, capture_output=True)
        assert r.returncode == 0, r.stderr.decode(errors="replace")[-500:]
        return r

    def sign(self, entry: dict) -> dict:
        sig = self.gpg(["--armor", "--detach-sign", "--output", "-"], SD.signed_payload(entry)).stdout.decode()
        return {**entry, "signature": sig}

    def close(self):
        subprocess.run(["gpgconf", "--kill", "all"], env=self.env, capture_output=True)
        shutil.rmtree(self.home, ignore_errors=True)


def tree(d: Path, keys: dict[str, bytes], frozen: dict[str, str], roots=("keys",)) -> Path:
    """A tree with keys/, tools/freeze.py (FROZEN_ROOTS = roots) and FROZEN.sha256 listing `frozen` {path: sha256}."""
    (d / "keys").mkdir(parents=True, exist_ok=True)
    (d / "tools").mkdir(exist_ok=True)
    for f in (d / "keys").iterdir():
        f.unlink()
    for name, b in keys.items():
        (d / "keys" / name).write_bytes(b)
    (d / "tools" / "freeze.py").write_text(f"FROZEN_ROOTS = {list(roots)!r}\n")
    (d / "FROZEN.sha256").write_text("".join(f"{h}  {f}\n" for f, h in sorted(frozen.items())))
    return d


class TestSignatureClaims(unittest.TestCase):
    def acc(self, kind, **kw):
        return {"kind": kind, "facts": {}, **kw}

    def test_a_claimed_signature_is_verified_and_fails_without_a_frozen_key(self):
        self.assertEqual(SD.frozen_keys(ROOT)[0], [], "no key is frozen at HEAD")
        e = {"kind": "weakening", "law_id": "L_x", "signature": SIG}
        why = SD._verify_committed(e, self.acc("weakening", signature="verified against keys/"), head(), ROOT)
        self.assertIsNotNone(why)
        self.assertIn("no public key is frozen", why)

    def test_a_claim_with_no_signature_fails_and_never_skips_the_equivalence(self):
        e = {"kind": "binding_change", "law_id": "L_x", "milestone": "M3"}
        with mock.patch.object(SD, "_verify_equivalence", side_effect=AssertionError("must not be reached")):
            why = SD._verify_committed(e, self.acc("binding_change", signature="verified against keys/"), head(), ROOT)
        self.assertIsNotNone(why)
        self.assertIn("signature", why)

    def test_an_unsigned_binding_change_runs_the_kernels_only_in_its_own_milestone(self):
        e = {"kind": "binding_change", "law_id": "L_x", "milestone": "M3"}
        with mock.patch.object(SD, "_verify_equivalence", return_value=None) as m:
            self.assertIsNone(SD._verify_committed(e, self.acc("binding_change"), head(), ROOT))
            self.assertIsNone(SD._verify_committed(e, self.acc("binding_change"), head(), ROOT, recheck=False))
        self.assertEqual([c.kwargs.get("kernels") for c in m.call_args_list], [True, False])
        with mock.patch.object(SD, "_verify_equivalence", return_value="bend2 no longer accepts it"):
            self.assertEqual(SD._verify_committed(e, self.acc("binding_change"), head(), ROOT),
                             "bend2 no longer accepts it")


class TestFrozenKeys(unittest.TestCase):
    """Only a key the human froze verifies a signature (F38 review M1)."""

    @classmethod
    def setUpClass(cls):
        cls.human, cls.agent = Gpg("HOLON F38 human <human@holon.invalid>"), Gpg("HOLON F38 agent <agent@holon.invalid>")
        cls.entry = cls.human.sign({"kind": "weakening", "law_id": "L_x", "old": LAW, "new": LAW, "review": "r"})

    @classmethod
    def tearDownClass(cls):
        cls.human.close()
        cls.agent.close()

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="f38-tree-"))

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_a_frozen_key_verifies_and_nothing_else_does(self):
        pub, h = self.human.public, sha(self.human.public)
        cases = [  # (keys/, FROZEN.sha256, FROZEN_ROOTS, verifies)
            ({"human.asc": pub}, {"keys/human.asc": h}, ("keys",), True),
            ({"human.asc": pub}, {"keys/human.asc": h}, ("keys/human.asc",), True),
            ({"human.asc": pub}, {}, ("keys",), False),                                  # not listed
            ({"human.asc": pub}, {"keys/human.asc": h}, ("facts",), False),              # not under the freeze
            ({"human.asc": pub}, {"keys/human.asc": "0" * 64}, ("keys",), False),        # bytes differ from the listing
            ({"human.asc": pub}, {"keys/human.txt": h}, ("keys",), False),               # no key suffix
            ({"human.asc": pub}, {"keys/../human.asc": h}, ("keys",), False),            # not directly under keys/
            ({"human.asc": pub, "agent.asc": self.agent.public},                         # the agent's key is not frozen
             {"keys/agent.asc": sha(self.agent.public)}, ("keys",), False),
        ]
        for keys, frozen, roots, want in cases:
            with self.subTest(keys=sorted(keys), frozen=frozen, roots=roots):
                ok, why = SD.verify_signature(self.entry, tree(self.d, keys, frozen, roots))
                self.assertEqual(ok, want, why)
        tree(self.d, {"human.asc": pub}, {"keys/human.asc": h})
        ok, why = SD.verify_signature({**self.entry, "review": "another"}, self.d)
        self.assertFalse(ok, why)   # the signature covers the entry
        r = SD.check_entry(self.entry, self.d)
        self.assertTrue(r["ok"], r["reason"])   # a signed, reviewed weakening

    def test_a_committed_line_needs_the_key_frozen_with_the_same_bytes_when_it_was_appended(self):
        pub, h = self.human.public, sha(self.human.public)

        def commit(msg):
            for args in (["add", "-A"], ["-c", "user.email=t@holon.invalid", "-c", "user.name=t", "commit", "-qm", msg]):
                subprocess.run(["git", "-C", str(self.d), *args], check=True, capture_output=True)
            return subprocess.run(["git", "-C", str(self.d), "rev-parse", "HEAD"], capture_output=True,
                                  text=True).stdout.strip()

        subprocess.run(["git", "init", "-q", str(self.d)], check=True)
        tree(self.d, {"human.asc": pub}, {})
        before = commit("the key, not frozen")
        tree(self.d, {"human.asc": pub}, {"keys/human.asc": h})
        frozen = commit("the key, frozen")
        self.assertFalse(SD.verify_signature_at(self.entry, before, self.d)[0], "a key frozen later signs nothing earlier")
        self.assertTrue(*SD.verify_signature_at(self.entry, frozen, self.d))
        # the human later replaces the key: a line appended under the old key no longer verifies against the listing
        tree(self.d, {"human.asc": self.agent.public}, {"keys/human.asc": sha(self.agent.public)})
        self.assertFalse(SD.verify_signature_at(self.entry, frozen, self.d)[0])


class TestG2Scope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with mock.patch.object(bend, "check_equivalence", side_effect=AssertionError("a kernel ran outside its gate")):
            cls.out = SD.scan(ROOT / SD.LOG, ROOT, milestone="M0")

    def test_another_milestones_proofs_are_tied_here_but_not_run(self):
        out = self.out
        self.assertTrue(out["git"])
        self.assertEqual(out["problems"], [])
        bc = [x["line"] for x in out["entries"] if (x["entry"] or {}).get("kind") == "binding_change"]
        self.assertTrue(bc, "the log holds binding_change lines (M3's)")
        self.assertEqual(sorted(out.get("elsewhere", [])), sorted(bc))
        self.assertTrue(all(x["ok"] for x in out["entries"] if x["line"] in bc))
        self.assertIn("their own milestone's G2", out["note"])

    def test_a_tampered_record_fails_in_another_milestones_gate_too(self):
        item = next(x for x in self.out["entries"] if (x["entry"] or {}).get("kind") == "binding_change")
        e, commit = item["entry"], item["commit"]
        for key, path in (("proof_sha256", ()), ("models", ("new",))):
            acc = json.loads(json.dumps(e["accepted"]))
            if path:
                acc["equivalence"][key][path[0]] = "0" * 64
            else:
                acc["equivalence"][key] = "0" * 64
            with self.subTest(tampered=key), \
                    mock.patch.object(bend, "check_equivalence", side_effect=AssertionError("a kernel ran")):
                why = SD._verify_committed(e, acc, commit, ROOT, recheck=False)
                self.assertIsNotNone(why)

    def test_a_line_about_no_milestones_law_is_rechecked_by_every_gate(self):
        self.assertEqual(SD._law_milestone(ROOT, "L_sort_realize_rollup_363_4a64383b"), "M3")
        self.assertIsNone(SD._law_milestone(ROOT, "L_no_such_law"))
        self.assertIsNone(SD._law_milestone(ROOT, "../M3/L_sort_realize_rollup_363_4a64383b"))


class TestCheckerStack(unittest.TestCase):
    def test_the_environment_carries_only_the_registered_stack(self):
        with mock.patch.dict(os.environ, {"BUN_JSC_useJIT": "0", "BUN_JSC_maxPerThreadStackUsage": "1"}):
            env = bend._env()
        self.assertNotIn("BUN_JSC_useJIT", env)
        self.assertEqual(env["BUN_JSC_maxPerThreadStackUsage"],
                         str(int(bend.config()["bend"]["js_stack_mb"]) * 1024 * 1024))
        cfg = json.loads(json.dumps(bend.config()))
        cfg["bend"]["js_stack_mb"] = 7
        self.assertEqual(bend._env(cfg)["BUN_JSC_maxPerThreadStackUsage"], str(7 * 1024 * 1024))

    def test_the_stack_is_raised_in_the_checkers_process_only(self):
        before = resource.getrlimit(resource.RLIMIT_STACK)
        r = bend.run(["version"])
        self.assertEqual(r.code, 0, r.out[-300:])
        self.assertEqual(resource.getrlimit(resource.RLIMIT_STACK), before, "this process's RLIMIT_STACK is unchanged")
        self.assertEqual(r.argv[:2], bend.checker_cmd(), "the launcher execs the fingerprinted checker command")
        child = subprocess.run(bend._spawn_argv(["/bin/sh", "-c", "ulimit -S -s"]), capture_output=True, text=True,
                               env=bend._env())
        self.assertEqual(int(child.stdout.strip()) * 1024, bend.stack_limits()["rlimit_soft"], child.stderr)

    def test_a_deep_proof_gets_a_verdict_not_a_stack_overflow(self):
        body = "0n"
        for _ in range(20000):
            body = f"(1n + {body} : Nat)"
        for rhs, accepted in (("20000n", True), ("20001n", False)):
            with self.subTest(rhs=rhs), tempfile.TemporaryDirectory() as d:
                (Path(d) / "LAWS.bend").write_text(f"import Base\n\ndef f() -> Nat:\n  {body}\n\n"
                                                   f"law deep_eq:\n  {{f() == {rhs} : Nat}}\n")
                p = Path(d) / "PROOF.bend"
                p.write_text("import Base\nimport ./LAWS.bend as Laws\n\ndef Laws.deep_eq():\n  {==}\n")
                for kernel, check in (("bend2", bend.check), ("BendTT", bend.check_verdict)):
                    # a stack below bun's default (about 5 MB): the machine stack overflows, no verdict
                    with mock.patch.object(bend, "js_stack_bytes", return_value=4 * 1024 * 1024):
                        small = check(p, timeout=300)
                    self.assertTrue(bend.crashed(small), f"{kernel}: {small.out[-300:]}")
                    r = check(p, timeout=600)
                    self.assertFalse(bend.crashed(r) or bend.timed_out(r), f"{kernel}: {r.out[-300:]}")
                    self.assertEqual(r.ok, accepted, f"{kernel}: {r.out[-300:]}")


if __name__ == "__main__":
    unittest.main()
