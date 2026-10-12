"""I2: the meaning of every frozen statement is bound by hash to the kernel form of the definitions it reaches."""
import re
import shutil
import unittest
from pathlib import Path

from tests_m2._m2 import MILESTONES, ROOT, copy_repo, holon_module, item, load_json, records, run_holon

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def bindings(m: str, root: Path = ROOT) -> dict:
    return load_json(root / "spec" / "bindings" / f"{m}.json")


class TestBindings(unittest.TestCase):
    def test_bindings_cover_every_law(self):
        for m in MILESTONES:
            reg = load_json(ROOT / "laws" / m / "REGISTRY.json")["statements"]
            b = bindings(m)["laws"]
            self.assertEqual(sorted(b), sorted(reg))
            for lid, x in b.items():
                with self.subTest(law=lid):
                    self.assertEqual(x["statement_hash"], reg[lid])
                    self.assertTrue(x["cone"])
                    self.assertTrue(all(HEX64.match(h) for h in x["cone"].values()))

    def test_bindings_match_a_fresh_derivation(self):
        B = holon_module("holon.bindings")
        for m in MILESTONES:
            with self.subTest(milestone=m):
                self.assertEqual(B.derive(m, ROOT)["laws"], bindings(m)["laws"])

    def test_dependents_match_prediction(self):
        want = {}
        for pid in ("I2-P1", "I2-P2", "I2-P3"):
            want.update(item("I2", pid)["expected"])
        deps = {}
        for m in MILESTONES:
            for d, ls in load_json(ROOT / "results" / m / "deps.json")["dependents"].items():
                deps.setdefault(d, set()).update(ls)
        for d, ls in want.items():
            with self.subTest(definition=d):
                self.assertEqual(sorted(deps.get(d, ())), sorted(ls))

    def test_kernel_cone_equals_token_cone(self):
        B = holon_module("holon.bindings")
        for m in MILESTONES:
            b = bindings(m)["laws"]
            for lid, rec in records(m).items():
                with self.subTest(law=lid):
                    own = B.model_definitions(m, rec, ROOT)
                    kernel = sorted(d for d in b[lid]["cone"] if d in own)
                    self.assertEqual(kernel, rec["cone"])

    def test_defs_index_is_generated_and_complete(self):
        for m in MILESTONES:
            for f in sorted((ROOT / "gen" / m / "model").glob("*.defs.json")):
                with self.subTest(index=f.name):
                    idx = load_json(f)["defs"]
                    self.assertTrue(idx)
                    for name, x in idx.items():
                        self.assertTrue(HEX64.match(x["sha256"]), name)
                        self.assertTrue(set(x["refs"]) <= set(idx), f"{name} refers outside the index")


def gate(repo: Path, m: str, checks: str):
    rp = repo / f"g_{m}.json"
    p = run_holon(["gate", "--milestone", m, "--root", str(repo), "--report", str(rp), "--checks", checks], cwd=repo)
    return p, (load_json(rp) if rp.exists() else None)


class TestBindingTamper(unittest.TestCase):
    ROLLUP = sorted(item("I2", "I2-P1")["expected"]["step_finalizeBatch"])

    def edited(self, edit):
        repo = copy_repo()
        try:
            f = repo / "gen" / "M1" / "model" / "morph_rollup.bend"
            text = f.read_text()
            new = edit(text)
            self.assertNotEqual(new, text, "the edit must change the file")
            f.write_text(new)
            p, rep = gate(repo, "M1", "G2")
            self.assertIsNotNone(rep, p.stdout[-1500:] + p.stderr[-1500:])
            return rep["checks"]["G2"]
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    @staticmethod
    def named_laws(detail: str) -> list[str]:
        return sorted(set(re.findall(r"\bL_[A-Za-z0-9_]+", detail)))

    def test_b_tags_exact_body_change_names_only_L_tag_BVH(self):
        def edit(t):
            i = t.index("def b_tags_exact(")
            j = t.index("True{}", i)
            return t[:j] + "False{}" + t[j + len("True{}"):]
        g2 = self.edited(edit)
        self.assertFalse(g2["passed"])
        self.assertIn("b_tags_exact", g2["detail"])
        self.assertEqual(self.named_laws(g2["detail"]), ["L_tag_BVH"])

    def test_step_finalize_change_names_the_rollup_laws(self):
        def edit(t):
            i = t.index("def step_finalizeBatch(")
            j = t.index("who, idx)\n", i)
            return t[:j] + "idx, who)\n" + t[j + len("who, idx)\n"):]
        g2 = self.edited(edit)
        self.assertFalse(g2["passed"])
        self.assertIn("step_finalizeBatch", g2["detail"])
        self.assertEqual(self.named_laws(g2["detail"]), self.ROLLUP)

    def test_alpha_rename_keeps_g2(self):
        def edit(t):
            i = t.index("def b_tags_exact(")
            k = t.index("\ndef ", i + 1)
            body = t[i:k].replace("es: List", "xs: List").replace("match es:", "match xs:")
            return t[:i] + body + t[k:]
        g2 = self.edited(edit)
        self.assertTrue(g2["passed"], g2["detail"])

    def test_comment_keeps_g2(self):
        g2 = self.edited(lambda t: t.replace("def b_tags_exact(", "# a comment changes no kernel entry\ndef b_tags_exact(", 1))
        self.assertTrue(g2["passed"], g2["detail"])


def signed_binding_change(repo: Path, lid: str, defs: list) -> int:
    """Append to the copy's laws/STATEMENT_DIFF.jsonl a binding_change entry for law lid (statement unchanged)
    naming defs, signed with a key made for the test in a throwaway GNUPGHOME and exported to the copy's keys/
    (holon.statement_diff.append checks it). Returns its line number. A signature is a human act: this key lives
    only in the throwaway copy."""
    import json
    import os
    import subprocess
    import tempfile
    SD = holon_module("holon.statement_diff")
    law = load_json(repo / "laws" / "M1" / f"{lid}.json")
    entry = {"kind": "binding_change", "law_id": lid, "old": law, "new": law, "defs": sorted(defs),
             "reason": "test: the planted change of " + ", ".join(sorted(defs))}
    home = Path(tempfile.mkdtemp(prefix="holon-test-gpg-"))
    try:
        os.chmod(home, 0o700)
        env = {"GNUPGHOME": str(home), "PATH": os.environ.get("PATH", ""), "LC_ALL": "C"}

        def gpg(*a):
            r = subprocess.run(["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", "", *a], env=env,
                               capture_output=True)
            if r.returncode != 0:
                raise AssertionError(f"gpg {a[:2]}: {r.stderr.decode(errors='replace')[-400:]}")
            return r.stdout
        gpg("--quick-gen-key", "holon test <test@holon.invalid>", "ed25519", "sign", "never")
        (repo / "keys").mkdir(exist_ok=True)
        (repo / "keys" / "test.asc").write_bytes(gpg("--armor", "--export", "test@holon.invalid"))
        (home / "payload").write_bytes(SD.signed_payload(entry))
        gpg("--armor", "--detach-sign", "--local-user", "test@holon.invalid", "-o", str(home / "sig.asc"),
            str(home / "payload"))
        entry["signature"] = (home / "sig.asc").read_text()
    finally:
        shutil.rmtree(home, ignore_errors=True)
    r = SD.append(entry, repo)
    if not r["ok"]:
        raise AssertionError(r)
    lines = [ln for ln in (repo / "laws" / "STATEMENT_DIFF.jsonl").read_text().splitlines()]
    assert json.loads(lines[-1])["law_id"] == lid
    return len(lines)


class TestBindChannel(unittest.TestCase):
    def test_rebind_requires_a_reason(self):
        repo = copy_repo()
        try:
            f = repo / "gen" / "M1" / "model" / "morph_rollup.bend"
            t = f.read_text()
            i = t.index("def b_tags_exact(")
            j = t.index("True{}", i)
            f.write_text(t[:j] + "False{}" + t[j + len("True{}"):])
            p = run_holon(["bind", "--milestone", "M1"], cwd=repo)
            self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("L_tag_BVH", p.stdout + p.stderr)
            # I10 lifecycle (audit M2/1 F-M2-09): a free-text reason alone no longer rebinds an existing law
            p = run_holon(["bind", "--milestone", "M1", "--accept-change", "test: planted change"], cwd=repo)
            self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("binding_change", p.stderr)
            # with an accepted binding_change entry naming the law and the changed definition, it does
            n = signed_binding_change(repo, "L_tag_BVH", ["b_tags_exact"])
            p = run_holon(["bind", "--milestone", "M1", "--accept-change", "test: planted change"], cwd=repo)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            log = (repo / "spec" / "bindings" / "changes.jsonl").read_text().strip().splitlines()
            last = __import__("json").loads(log[-1])
            self.assertEqual(last["reason"], "test: planted change")
            self.assertEqual(last["laws"], ["L_tag_BVH"])
            self.assertIn("b_tags_exact", last["defs"])
            self.assertEqual(last["covered_by"], {"L_tag_BVH": n})
            p, rep = gate(repo, "M1", "G2")
            self.assertTrue(rep["checks"]["G2"]["passed"], rep["checks"]["G2"]["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
