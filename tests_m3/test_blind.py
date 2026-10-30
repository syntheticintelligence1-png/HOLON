"""I82 (= I46a): the blind pack, the comparison generator and the agreement metric (BUILD_PLAN row I82; I46 keeps its
number for the blind rerun and the M3 exit). This docstring is the contract. The independent instrument is
tests_m3/_i82.py (it imports nothing from holon/); its sha256 and this docstring's are pinned in the key I82 of
spec/M3/predictions.json. Sidecars, fixed at the prereg: spec/M3/lib/blind_pack.json (the pack's protocol) and
spec/M3/lib/appendixA.json (the map's record sets, back-tests and curated links).

The pack (tools/blind_pack.py)
  K1 `python tools/blind_pack.py [--root DIR] [--commit C] [--target PATH] --out DIR` packs commit C (default HEAD) of
     the repository at ROOT. It reads spec/M3/lib/blind_pack.json from C's tree (never the working tree) and the target
     from the checkout at --target (default: config/holon.json extract.sources[target.repo], read from C) at the
     sidecar's target.commit. It writes DIR/bundle.tar, DIR/manifest.json and DIR/leaks.json and exits 0; a missing
     commit, sidecar or target object is exit 2 with a message, and nothing is written.
  K2 Every byte comes from git objects: C's tree for HOLON (git ls-tree -r, git cat-file), target.commit's tree for the
     target. Uncommitted edits, untracked files and the working trees' state never enter the bundle.
  K3 Members. target/<p> for every blob of the target commit's tree (gitlinks, mode 160000, are not packed and are
     listed in the manifest's excluded.target). tooling/<p> for every blob p of C that is an include_files entry or
     lies under an include_roots entry, unless p starts with an exclude_prefixes entry, p's basename matches an
     exclude_basenames pattern (fnmatch), or p is an exclude_paths key (checked in that order). tooling/whitepaper.md
     is C's whitepaper.md redacted by K5. Nothing else. A symlink blob (mode 120000) is packed as a symlink whose
     target is the blob's bytes.
  K4 Format: an uncompressed POSIX tar (pax), members sorted by member path (UTF-8 bytes), no directory entries; every
     member has mtime 0, uid 0, gid 0, empty uname and gname; mode 0o755 for a git mode 100755 blob, 0o644 otherwise.
  K5 Redaction. Headings are lines starting with "#" outside fenced code blocks (a line starting with ``` toggles a
     fence); a heading's level is its number of leading "#". Each remove_sections entry names the heading line that
     starts with it; its section runs from that line to the line before the next heading of the same or a higher level
     (as many "#" or fewer), or to the end. A remove_lists line is the line equal to the entry (trailing blanks
     ignored) outside the removed sections; it is removed with every following line up to and including the first
     blank line after it. Nothing else changes: the redacted text is the original lines (split at "\\n") minus those
     spans, joined with "\\n". The manifest's redactions list each removed span in line order: what (the entry), start
     (its first line, 1-based, in C's file), lines (how many removed) and sha256 (of the removed lines joined with
     "\\n").
  K6 manifest.json: pack_version (the sidecar's version), holon {commit, tree}, target {repo, commit, tree},
     sidecar {path, sha256}, members [{path, size, sha256, mode, source: holon | target | redacted}] in member order,
     excluded {holon: {prefix, basename, path: [sorted paths]}, target: [sorted gitlink paths]}, where holon lists
     every blob of C under an include root or include file that K3 does not pack, under the first rule that excludes
     it; redactions; leaks (L4's summary); bundle {sha256, size, members}. No output records where or when it was
     made: no absolute path of the packing machine, host name, time or user name (L3's excerpts and matches quote the
     packed text as it is).
  K7 Determinism: the same commit, target commit and sidecar give byte-identical bundle.tar, manifest.json and
     leaks.json, whatever the working directory, TZ, umask, locale, output directory and working-tree state.
  K8 JSON outputs: json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\\n", UTF-8.
  K9 So facts/, spec/, laws/, gen/, results/, replay/, docs/ and prompts/ are absent (exclude_prefixes), and so are
     tests/, tests_m*/ and audit/ (no include root), the maps_to sidecars and spec/M1/policy_hints.mjs.

The leak scan (tools/blind_pack.py, in the same run)
  L1 Scope: every regular member whose path starts with leaks.scan_prefix (tooling/: the tooling and the redacted
     whitepaper). The target code is the subject of analysis and is not scanned. A member that is not valid UTF-8 is
     listed under leaks.json's unscanned, never skipped silently.
  L2 Classes. section_ref, case_id and code_site: the sidecar's regexes (Python re), per line. law_name: every
     basename stem of laws/M0/L*.json and laws/M1/L*.json in C's tree, and every row name of the table under the
     heading "### 11.8" of C's whitepaper.md (its rows: lines starting with "|" before the next heading, less the
     header line and the separator line; a row name: the first cell with every parenthesized part removed, split at
     "," and stripped, so "L_sym_ω(zk, challenge)" names L_sym_ω), each matched as a literal not preceded or followed by
     [A-Za-z0-9_]. witness: every number in the text K5 removes as sections (a match of \\d{1,3}(?:,\\d{3})+|\\d+ not
     preceded by [A-Za-z0-9_.,] and not followed by [A-Za-z0-9_,] or by "." and a digit) with at least min_digits
     digits once its commas are removed, matched in either form (plain, or grouped with a comma every three digits from
     the right) under the same boundary conditions.
  L3 Lines are the member's text split at "\n". A match: {path (the member path), line (1-based), col (0-based
     start), class, match (the matched text), excerpt
     (the line stripped, then cut to 200 characters)}, plus rule_context for case_id (true iff the sidecar's
     rule_context regex is found in the context_chars characters before the match on its line). One match per (path,
     line, col, class): at one start, the first of the class's patterns that matches there (sidecar order; law_name
     and witness literals in sorted order; every start of every pattern is tried, re.finditer). Matches are sorted by
     (path, line, col, class, match).
  L4 leaks.json: {scanned: [member paths], unscanned: [member paths], law_names: [sorted], witness_numbers: [sorted
     plain strings], matches: [...], summary}. summary = {by_class: {class: n}, files_by_class: {class: n files}} over
     all five classes (0 allowed), and by_root: {root: {class: n}} with only counts n >= 1, root being the member path's
     first two segments (tooling/holon, tooling/whitepaper.md, ...). The manifest's leaks is this summary.
  L5 Nothing is filtered or allow-listed: the scan reports pattern matches, not adjudicated leaks.
  L6 The pack's exit status does not depend on the leak list.

The map and the comparison (holon/report.py)
  A1 `python -m holon report --milestone M3 [--root DIR] [--check] [--results SET=DIR ..]` writes
     spec/M3/appendixA_map.json and docs/M3_COMPARISON.md under ROOT; --check writes nothing and exits 1 iff either file
     differs from its regeneration or is missing, 0 otherwise; --results puts DIR in place of that set's results
     directory. Both outputs are pure functions of the inputs (the map in K8's form); no timestamp, timing or absolute
     path.
  A2 The catalog, parsed from ROOT's whitepaper.md (tables: lines starting with "|"): section 11.3's rows (O<n>, rule,
     title, prior = the F<n> and N<n> tokens of the Prior cell as written, e.g. F12.1 or F11b,c), section 11.4's
     "**N<n> (O<m>).**" pairs, section 11.6's D<n> rows, Appendix A's F<n> rows, and the section 11.8 table's rows as
     R1, R2, .. in order (name = first cell, names = its row names as in L2, rule, prediction, witness). A rule's
     families: the cell split at "×" and "/", each part's text before the first "-", " " or "(" (PAR-domain -> PAR;
     SORT×UNDO -> SORT, UNDO; FACT/SORT -> FACT, SORT).
  A3 Record sets: the sidecar's sets, in order; a set is read iff its results directory exists. Its laws are the
     L*.json of its laws directory that have a record (results/<..>/<law_id>.json); a law's status is the record's
     status. The hypotheses set (sidecar ledger.hypotheses_set, basis code) holds the ledger's hypotheses, each with
     the status of its entry in ledger.hypotheses_results and rule HYP.
  A4 Generated links. (maps_to) a law of a set whose IR, or else record, carries a string maps_to: the O<n> and D<n>
     tokens of its text before the first "(" (split at "/" and blanks); (ledger) spec/ledger/maps_to.json's M0 lists for
     the ledger set and its hypotheses for the hypotheses set; (name) a law of a set with a predictions file is linked
     to row R iff its id equals one of R's names, starts with one of them followed by "_", or equals one of them with
     ω written omega; (backtest) for every row of each sidecar back-test whose new key names a law, that law (in the
     back-test's set) inherits every non-backtest link of the old law (in its against set), item and expect copied,
     via "<path>: <old law>". A sidecar link is (sidecar).
  A5 Expect (the status that agrees with the whitepaper's manual result). (maps_to), (ledger): D items PROVED (a
     hypothesis: checked); O items whose families exclude DISCH: REFUTED; other O items: the law's status in its set's
     predictions file (entries with post_hoc true excluded), else null. (name): that predictions status (post_hoc
     excluded), else null. (backtest): the inherited link's expect. (sidecar): as written. A sidecar override replaces
     the expect of the generated links with the same item, set and law.
  A6 A link is counted iff its expect is not null and, for an O item, the law's rule is one of the item's families
     (hypotheses count for D items only). Links are unique per (item, set, law): the first source in the order
     sidecar, maps_to, ledger, name, backtest wins and the later ones are listed in its also field (their via, or their
     source name when they have none).
  A7 The map (spec/M3/appendixA_map.json): version; inputs {path: sha256} of whitepaper.md, the sidecar,
     docs/BUILD_PLAN.md, the ledger, the hypotheses results, and the sets' predictions files and the back-test files
     that exist; sets [{name, basis, laws, results, n_laws}] (the sets read, the hypotheses set last); items {id: ...}
     for every O1-O37, D1-D9, N1-N4, F1-F14 and R1-R14: O {kind obstruction, rule, families, title, prior, planned,
     links}, D {kind discharged, title, planned, links}, N {kind new, o, title}, F {kind prior, title, via: [{o, cited}]
     (the O items whose prior cites F<n> or F<n> with a sub-item, and what they cite)}, R {kind row, name, names, rule,
     prediction, witness, links}; each link {set, law, rule, expect, counted, source, via, also}, links sorted by (set
     order, law); unmapped {set: [the laws of a code set that no link reaches]}; absent [sidecar links whose law has no
     record in its set, as written]. planned (O and D items): the names (the heading text between "#### " and the first
     ".") of the docs/BUILD_PLAN.md sections whose heading starts with "#### I" and whose text, up to the next heading
     line, matches \\b<id>\\b, in file order.
  A8 Verdicts, per item and basis (hand: the hand sets; code: the code sets and the hypotheses set), over that basis's
     links, a link's status being its law's status (a law without a record: "no record", never equal to an expect;
     decided: PROVED, REFUTED, checked or failed). O items (some): reproduced if a counted link's status equals its
     expect; else contradicted if a counted link is decided and differs; else open if the basis has a link; else not
     mechanized. D items and rows (all): certified (D) or held (row) if there is a counted link and every counted link's
     status equals its expect; else contradicted (D) or missed (row) if a counted link is decided and differs; else
     open if the basis has a link; else not mechanized. N: its O item's verdict. F, over the O items its via names:
     reproduced if all are reproduced; partly reproduced if some are; else contradicted if some are; else open if some
     is open; else not mechanized (also when no O item cites it).
  A9 docs/M3_COMPARISON.md: the contamination caveat; a section 11.7-style summary (per basis, the F ids per verdict);
     one table line per item, cells separated by " | " ("|" inside a cell written "\\|", a newline as a space):
       "| R<n> | name | rule | prediction | hand links | hand verdict | code links | code verdict |"
       "| F<n> | finding | O items | hand verdict | code verdict |"
       "| O<n> | rule | prior | hand links | hand verdict | code links | code verdict | planned |"
       "| D<n> | obligation | hand links | hand verdict | code links | code verdict | planned |"
       "| N<n> | O item | hand verdict | code verdict |"
     a link written "<law> (<set>) <status>", " (context)" appended when it is not counted, links joined with "; ",
     "—" for none; the unmapped laws per set; the inputs with their sha256.
  G1 holon gate's G1, for a milestone m whose spec/<m>/lib/appendixA.json exists and whose root's whitepaper.md has a
     "### 11.8" heading, regenerates the map and the comparison with m's regenerated records in place of the set named
     m (holon.report.regenerate_check) and compares both byte for byte with the committed files; a difference or a
     missing file fails G1. Without the heading (a blind bundle's redacted whitepaper) its detail says the comparison
     was not regenerated.

The agreement metric (holon/blind.py)
  B1 `python -m holon compare --blind DIR [--lead DIR] [--milestone M[,M..]] [--out FILE] [--threshold X]`, the lead
     defaulting to the repository root and the milestone to M3. A tree is a directory with laws/<M>/L*.json (law IR)
     and results/<M>/L*.json (records); a law is recorded iff results/<M>/<law_id>.json holds a string status.
  B2 The alpha-normal form of a statement: binders (holon-ir/0.1 forall; later binders, with q) renamed x0, x1, .. in
     binder order wherever a binder name occurs as {"var": n}, {"app": n} or a cf premise's fn; premises as a sorted
     set of canonical JSON; each eq/neq with its two sides sorted by canonical JSON; a top-level conjunction (all) as
     a sorted set; binder quantifiers and types kept; scope kept (unbounded when absent). The law id, facts path and
     hash, rule, notes and every other field are not part of it. A statement of another shape is normalized as its
     canonical JSON. The key is sha256 of the canonical JSON (K8's canonical form: sort_keys, separators (",", ":"),
     ensure_ascii=False) of the normal form.
  B3 Classes: per tree and milestone, the recorded laws grouped by key; a class's status is its members' common
     status, or "MIXED:" + "+".join(sorted(set(statuses))) when they differ.
  B4 Per milestone: lead_keys and blind_keys (class counts); matched (keys in both); agree (matched keys with equal
     class status); blind_agreement = agree / matched (null when matched is 0); matched_fraction = matched / lead_keys
     (null when lead_keys is 0); lead_only and blind_only (the sorted law ids of the unmatched classes); disagreements
     [{key, lead: {laws, status}, blind: {laws, status}}] sorted by key; unrecorded {lead, blind} (sorted law ids
     without a record); facts_differ [{key, lead, blind}] (the sorted facts paths of a matched class's laws, where the
     two sides differ), sorted by key.
  B5 Output: K8's form, to --out or stdout: {milestones: {M: {...B4}}, pooled: {lead_keys, matched, agree,
     blind_agreement, matched_fraction}} (pooled sums the counts over the milestones). Exit 0, or 1 when --threshold is
     given and the pooled blind_agreement is null or below it; a tree without laws/<M> or results/<M> is exit 2.
  B6 `python -m holon compare --snapshot SRC --into DST [--milestone M[,M..]]` copies SRC's laws/<M>/L*.json byte for
     byte and writes each recorded law's record as {"law_id", "status"} (K8's form) under DST: a committed projection of
     a scratch tree that B1 reads like any tree.

Commits
  R  I82's own commits are the non-merge commits of `git log --first-parent <C_K>..<end>`, end being the first commit
     adding docs/iterations/I82.md (HEAD before it exists). They change only tools/blind_pack.py, holon/report.py,
     holon/blind.py, holon/__main__.py, holon/gate.py, spec/M3/appendixA_map.json, docs/M3_COMPARISON.md, files under
     audit/blind/, docs/iterations/I82.md and tests_m3/test_blind.py (new tests only). None of them is in a generator
     closure (holon.records.generator_files for every IR version, holon.profile.generator_files and the generator_sha256
     closures of holon.sorts.run3, holon.undo.run, holon.fact.run, holon.disch.run and holon.versions.run), so no record
     is re-made. holon/report.py and holon/blind.py contain no law-id literal and import no test module.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m3 import _i82 as I

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "blind_pack.py"
MAP = ROOT / "spec" / "M3" / "appendixA_map.json"
DOC = ROOT / "docs" / "M3_COMPARISON.md"
DRYRUN = ROOT / "audit" / "blind" / "dryrun"


def _run(args, cwd=ROOT, env=None, timeout=3600):
    e = dict(os.environ)
    e.update(env or {})
    e["BEND_NO_TELEMETRY"] = "1"
    return subprocess.run(args, cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout)


def _holon(*args, cwd=ROOT, env=None, timeout=3600):
    e = dict(env or {})
    e["PYTHONPATH"] = str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")
    return _run([sys.executable, "-m", "holon", *args], cwd=cwd, env=e, timeout=timeout)


class _Pack(unittest.TestCase):
    """One pack of HEAD per test class, built by the tool into a scratch directory."""
    commit = None
    out = None

    @classmethod
    def setUpClass(cls):
        cls.commit = I.git(ROOT, "rev-parse", "HEAD").strip()
        cls.tmp = Path(tempfile.mkdtemp(prefix="i82-pack-"))
        cls.out = cls.tmp / "out"
        cls.proc = _run([sys.executable, str(TOOL), "--root", str(ROOT), "--commit", cls.commit, "--out", str(cls.out)])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)


class TestPack(_Pack):
    def test_p1_the_bundle_holds_exactly_the_protocols_members(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stdout + self.proc.stderr)
        exp = I.expected_members(ROOT, self.commit)
        got = I.tar_members(self.out / "bundle.tar")
        self.assertEqual(sorted(got), sorted(exp["members"]), "member set")
        for path, want in exp["members"].items():
            self.assertEqual(got[path], want, path)
        self.assertEqual(I.forbidden_members(ROOT, self.commit, got), [], "a protocol-excluded path is packed")
        self.assertEqual(I.tar_format_problems(self.out / "bundle.tar"), [])
        man = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(I.manifest_problems(ROOT, self.commit, man, exp, self.out), [])

    def test_p2_the_pack_is_byte_identical_across_runs_and_environments(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stdout + self.proc.stderr)
        other = self.tmp / "elsewhere" / "deep" / "out2"
        p = _run([sys.executable, str(TOOL), "--root", str(ROOT), "--commit", self.commit, "--out", str(other)],
                 cwd=self.tmp, env={"TZ": "Pacific/Kiritimati", "LC_ALL": "C", "LANG": "C"})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        for name in ("bundle.tar", "manifest.json", "leaks.json"):
            self.assertEqual(I.sha256_file(self.out / name), I.sha256_file(other / name), name)

    def test_p3_the_whitepaper_is_redacted_as_the_protocol_says(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stdout + self.proc.stderr)
        exp_text, spans = I.redact(ROOT, self.commit)
        got = I.tar_read(self.out / "bundle.tar", "tooling/whitepaper.md").decode("utf-8")
        self.assertEqual(got, exp_text)
        self.assertEqual(I.redaction_prediction_problems(got, spans), [])
        man = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(man["redactions"], spans)

    def test_p4_the_leak_scan_finds_what_the_instrument_finds_and_it_is_not_empty(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stdout + self.proc.stderr)
        got = json.loads((self.out / "leaks.json").read_text(encoding="utf-8"))
        exp = I.leak_scan(ROOT, self.commit, self.out / "bundle.tar")
        self.assertEqual(got, exp)
        self.assertEqual(I.leak_prediction_problems(got), [])


class TestMap(unittest.TestCase):
    def test_p5_the_map_links_every_item_by_its_generated_and_sidecar_sources(self):
        doc = json.loads(MAP.read_text(encoding="utf-8"))
        self.assertEqual(I.map_problems(ROOT, doc), [])

    def test_p6_the_comparison_regenerates_byte_identically_and_g1_covers_it(self):
        p = _holon("report", "--milestone", "M3", "--check")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(I.g1_comparison_problems(ROOT, _holon), [])

    def test_p7_every_f_id_has_a_cell_and_every_verdict_follows_the_rules(self):
        doc = json.loads(MAP.read_text(encoding="utf-8"))
        text = DOC.read_text(encoding="utf-8")
        self.assertEqual(I.comparison_problems(ROOT, doc, text), [])


class TestMetric(unittest.TestCase):
    def test_p8_the_dry_run_on_the_leads_regenerated_records_agrees_fully(self):
        rep = json.loads((DRYRUN / "compare.json").read_text(encoding="utf-8"))
        self.assertEqual(I.dry_run_problems(ROOT, DRYRUN, rep), [])
        p = _holon("compare", "--blind", str(DRYRUN / "tree"), "--lead", str(DRYRUN / "lead"),
                   "--milestone", ",".join(I.DRY_RUN_MILESTONES))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(json.loads(p.stdout), rep)

    def test_p9_synthetic_perturbations_move_the_metric_exactly(self):
        tmp = Path(tempfile.mkdtemp(prefix="i82-perturb-"))
        try:
            for case in I.perturbation_cases(ROOT, tmp):
                args = ["compare", "--blind", str(case["blind"]), "--lead", str(case["lead"]),
                        "--milestone", ",".join(case["milestones"])] + case.get("args", [])
                p = _holon(*args)
                self.assertEqual(p.returncode, case["exit"], case["name"] + ": " + p.stdout[-2000:] + p.stderr[-2000:])
                if case["exit"] == 0:
                    self.assertEqual(I.perturbation_problems(case, json.loads(p.stdout)), [], case["name"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestRegressions(unittest.TestCase):
    def test_r0_the_prereg_pins_hold(self):
        th = json.loads((ROOT / "spec" / "M3" / "predictions.json").read_text(encoding="utf-8"))["iterations"]["I82"][
            "thresholds"]
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])
        self.assertEqual(I.sha256_file(ROOT / th["instrument"]), th["instrument_sha256"])
        for k in ("pack_sidecar", "map_sidecar"):
            self.assertEqual(I.sha256_file(ROOT / th[k]["path"]), th[k]["sha256"], k)

    def test_r1_own_commits_touch_only_what_the_contract_allows(self):
        self.assertEqual(I.own_commit_problems(ROOT), [])

    def test_r2_the_prereg_audits_pass(self):
        for m in ("M2", "M3"):
            p = _holon("audit", "prereg", "--milestone", m)
            self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-3000:])

    def test_r3_no_generator_closure_file_changes_and_holon_names_no_law(self):
        self.assertEqual(I.closure_and_naming_problems(ROOT), [])


if __name__ == "__main__":
    unittest.main()
