"""I14 honesty: the evidence set is computed from the diagram and the frozen assignment, never from hand annotations,
docs or the facts' own spelling of names (BUILD_PLAN I14 Goal "Compute evidence levels from 𝔇"; AGENTS rules 2 and 4;
the contract is the docstring of tests_m2/test_evidence.py).

It reuses I13's mutations (tests_m2/test_sorts_honesty.py, fixed at the I13 prereg). One copy of the repo is mutated
two ways; each time the diagram is regenerated in the copy (`holon diagram --milestone M2 --root COPY`), the sorts are
recomputed into the copy's gen/M2/sorts (`holon sorts --milestone M2 --root COPY --out COPY/gen/M2/sorts`) and
`holon evidence --milestone M2 --root COPY --out FILE` runs:
  baseline  unmodified (the fact documents re-dumped, as for the other variants);
  strip     every "site" and "note" key, and every doc string stating sorts, sites or ghosts, removed from every fact
            document (I13's strip). No level reads a note, a doc or a site annotation, and E6 reads code identifiers
            only, so the atoms, the unresolved entries and the anchors are the baseline's, ids included;
  rename    the rollup facts' hand-chosen identifiers renamed consistently (I13's rename: state fields t, W, F, D,
            qpend, qlen, enq, s_bvh; input wait.dt; lets cstart, prt, btot, bn, ef; docs, src strings, action names
            and record fields untouched). Every atom and unresolved entry is the baseline's under the renaming (ids
            aside: an id hashes its via), and so are the anchors (site ids aside: an I13 site id hashes its expression
            as written). A level that keyed on a facts name would move.
"""
import json
import re
import shutil
import unittest
from collections import Counter

from tests_m2._m2 import copy_repo, load_json, run_holon
from tests_m2.test_sorts_honesty import (LEAF_RN, ROLLUP, dump, fact_paths, rename_identifiers, strip_hints,
                                         strip_state_docs)

ROLLUP_MODEL = "morph_rollup"
INVERSE = {v: k for k, v in LEAF_RN.items()}
_RENAMED = re.compile(r"\b(" + "|".join(sorted(map(re.escape, INVERSE), key=len, reverse=True)) + r")\b")


def unrename(obj):
    """obj with every renamed identifier mapped back (on its JSON text: the new names are unique zz_ tokens)."""
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return json.loads(_RENAMED.sub(lambda m: INVERSE[m.group(1)], text))


def bag(doc: dict, key: str, back: bool = False) -> Counter:
    """The entries of doc[key] without their ids (renamed back when `back`), as a multiset of canonical JSON."""
    out = Counter()
    for x in doc[key]:
        y = {k: v for k, v in x.items() if k != "id"}
        out[json.dumps(unrename(y) if back else y, sort_keys=True, ensure_ascii=False)] += 1
    return out


def without_site_hashes(anchors: dict) -> dict:
    a = dict(anchors)
    a["sites"] = {k.rsplit(":", 1)[0]: v for k, v in (anchors.get("sites") or {}).items()}
    return a


class TestEvidenceHonesty(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        try:
            cls._run_all()
        except BaseException:
            shutil.rmtree(cls.repo.parent, ignore_errors=True)
            raise

    @classmethod
    def _run_all(cls):
        repo = cls.repo
        orig = {p: json.loads(p.read_text(encoding="utf-8")) for p in fact_paths(repo)}
        rollup = repo / ROLLUP

        def strip_all():
            for p, f in orig.items():
                dump(p, strip_state_docs(strip_hints(f)))

        def rename_all():
            dump(rollup, rename_identifiers(orig[rollup]))

        cls.runs = {}
        for name, mutate in (("baseline", None), ("strip", strip_all), ("rename", rename_all)):
            for p, f in orig.items():
                dump(p, f)
            if mutate:
                mutate()
            out = repo / f"evidence_{name}.json"
            logs, ok = [], True
            for args in (["diagram", "--milestone", "M2", "--root", str(repo)],
                         ["sorts", "--milestone", "M2", "--root", str(repo), "--out", str(repo / "gen" / "M2" / "sorts")],
                         ["evidence", "--milestone", "M2", "--root", str(repo), "--out", str(out)]):
                p = run_holon(args, cwd=repo)
                logs.append(f"$ holon {args[0]} ({name}): exit {p.returncode}\n{p.stdout[-1500:]}{p.stderr[-1500:]}")
                if p.returncode != 0:
                    ok = False
                    break
            cls.runs[name] = (ok, "\n".join(logs), load_json(out) if ok and out.exists() else None)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def ran(self, name: str) -> dict:
        ok, log, doc = self.runs[name]
        self.assertTrue(ok, log)
        self.assertIsNotNone(doc, f"{name}: holon evidence wrote nothing\n{log}")
        return doc

    def test_stripping_hand_hints_changes_no_atom(self):
        """strip: atoms, unresolved entries and anchors are the baseline's, ids included."""
        base, strip = self.ran("baseline"), self.ran("strip")
        self.assertTrue(any(a["model"] == ROLLUP_MODEL for a in base["atoms"]), "the baseline has rollup atoms")
        self.assertEqual(strip["atoms"], base["atoms"])
        self.assertEqual(strip["unresolved"], base["unresolved"])
        self.assertEqual(sorted(strip["models"]), sorted(base["models"]))
        for m in base["models"]:
            with self.subTest(model=m):
                self.assertEqual(strip["models"][m]["anchors"], base["models"][m]["anchors"])

    def test_renaming_fact_identifiers_renames_the_evidence_and_nothing_else(self):
        """rename: atoms, unresolved entries and anchors are the baseline's under the renaming."""
        base, rn = self.ran("baseline"), self.ran("rename")
        self.assertIn("zz_", json.dumps(rn["models"][ROLLUP_MODEL]["anchors"]),
                      "the renaming reached the evidence document (a carrier was renamed)")
        for key in ("atoms", "unresolved"):
            with self.subTest(part=key):
                got, want = bag(rn, key, back=True), bag(base, key)
                self.assertEqual(sorted((got - want).elements()), [], f"{key} the renaming created")
                self.assertEqual(sorted((want - got).elements()), [], f"{key} the renaming lost")
        for m in base["models"]:
            with self.subTest(model=m):
                self.assertEqual(without_site_hashes(unrename(rn["models"][m]["anchors"])),
                                 without_site_hashes(base["models"][m]["anchors"]))


if __name__ == "__main__":
    unittest.main()
