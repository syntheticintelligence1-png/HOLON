"""I95's build: the binding's pack inputs are code and facts, never outcomes (the lead's two conditions for #106).

H1  The three harness sources that spec/M3/lib/binding.json names hold no word or address of a committed deployment
    record (gen/M3/binding/*.json, its "deployment" member). The words are the storage keys and values, the
    preimages, the immutables, the addresses, and each 32-byte argument word and selector of a recorded call. A word
    counts once it has at least 4 significant bytes; smaller values, such as 1 or 10, occur in any code and identify
    nothing. A word that the target's own code at the record's commit contains (git grep in the configured checkout)
    is code, not an outcome of the deployment, and is reported in the message, not failed. Two such words occur at
    I95's build: the EIP-1967 implementation slot and the target's zero versioned hash constant. Each is matched
    case-insensitively, in hex and in decimal.
H2  The deployment parameters are read from the pack's copy of the M1 facts' initial members
    (spec/M3/lib/binding_facts.json, its copy_of the M1 facts). The copy gives its source's values for the keys, and
    holon binding refuses a copy whose values differ from its source's.
H3  The copy holds facts only: facts_copy_version, doc, copy_of, copy_of_sha256 and initial, whose members are
    exactly those the keys name. The scope's strip rules strip nothing from it.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from holon import binding as B

ROOT = Path(__file__).resolve().parents[1]


def _json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _words(x):
    """Every hex word or address under x: 32-byte chunks of long strings (after a 4-byte selector when the length
    says so), the selector itself, and every shorter hex string."""
    if isinstance(x, dict):
        for k, v in x.items():
            yield from _words(k)
            yield from _words(v)
    elif isinstance(x, list):
        for v in x:
            yield from _words(v)
    elif isinstance(x, str) and re.fullmatch(r"0x[0-9a-fA-F]+", x):
        h = x[2:].lower()
        if len(h) > 64:
            sel = (len(h) - 8) % 64 == 0
            body = h[8:] if sel else h
            for i in range(0, len(body), 64):
                yield body[i:i + 64]
            if sel:
                yield h[:8]
        else:
            yield h


def _checkout() -> Path:
    return Path(_json("config/holon.json")["replay"]["morph"])


class TestBindingInputs(unittest.TestCase):
    def test_h1_no_record_word_or_address_in_the_harness_sources(self):
        files = _json(B.spec_rel("M3"))["harness"]["files"]
        texts = {f: (ROOT / f).read_text(encoding="utf-8").lower() for f in files}
        records = sorted((ROOT / "gen" / "M3" / "binding").glob("*.json"))
        self.assertTrue(records)
        hits, code = [], []
        for rp in records:
            rec = json.loads(rp.read_text(encoding="utf-8"))
            words = {w.lstrip("0") for w in _words(rec["deployment"])}
            for w in sorted(x for x in words if len(x) >= 8):
                where = [f for f, t in texts.items()
                         if w in re.sub(r"[^0-9a-f]", "", t) or str(int(w, 16)) in t]
                if not where:
                    continue
                g = subprocess.run(["git", "-C", str(_checkout()), "grep", "-q", "-i", "-E", f"0*{w}",
                                    rec["inputs"]["commit"], "--"], capture_output=True)
                (code if g.returncode == 0 else hits).append((rp.name, w[:16], where))
        self.assertEqual(hits, [], f"record words in the harness sources (target code, not failed: {code})")

    def test_h2_the_parameters_are_read_from_the_facts_copy_and_checked(self):
        spec = _json(B.spec_rel("M3"))
        init = spec["init"]
        self.assertEqual(init["facts"], B.facts_rel("M3"))
        B.copy_check(ROOT, init)                    # the copy gives its source's values (refuses otherwise)
        copy = _json(B.facts_rel("M3"))
        self.assertTrue((ROOT / copy["copy_of"]).is_file())
        tmp = Path(tempfile.mkdtemp(prefix="i95_copy_"))
        try:
            bad = json.loads(json.dumps(copy))
            k0 = sorted(bad["initial"])[0]
            v = bad["initial"][k0]
            bad["initial"][k0] = [x + 1 for x in v] if isinstance(v, list) else v + 1
            (tmp / Path(init["facts"]).parent).mkdir(parents=True)
            (tmp / init["facts"]).write_text(json.dumps(bad), encoding="utf-8")
            (tmp / Path(copy["copy_of"]).parent).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / copy["copy_of"], tmp / copy["copy_of"])
            with self.assertRaises(B.BindingError):
                B.copy_check(tmp, init)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_h3_the_copy_holds_facts_only(self):
        spec, copy = _json(B.spec_rel("M3")), _json(B.facts_rel("M3"))
        self.assertEqual(set(copy) - {"facts_copy_version", "doc"}, {"copy_of", "copy_of_sha256", "initial"})
        self.assertEqual(set(copy["initial"]), {k.split(".")[0] for k in spec["init"]["keys"]})
        sys.path.insert(0, str(ROOT / "tests_m3"))
        import blind_scope as S
        sc = _json("spec/M3/lib/blind_rerun.json")["scope"]
        _, removed = S.strip(copy, re.compile(sc["strip_key_pattern"]), re.compile(sc["strip_hash_pattern"]),
                             S.leak_patterns(ROOT, "HEAD"))
        self.assertEqual(removed, [])


if __name__ == "__main__":
    unittest.main()
