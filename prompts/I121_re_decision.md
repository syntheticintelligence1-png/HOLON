# I121 (M6, generality): the re-decision

Branch `claude/i121-re-decision`, from the lead `claude/holon-v2-bend2-c6z3cd` at 65328226 (I119 (a)'s landing,
#201). When the lead moves, merge it with a merge commit, except while a counted run is going; never rebase, amend or
force-push. Branch only: the lead lands this key, after I118 (Q93 (1)(b)). Read AGENTS.md, docs/M0_SPEC.md,
docs/BEND_PRIMER.md, BUILD_PLAN §3 (row I121) and §4 "M6: generality", docs/iterations/I119.md and
docs/HUMAN_ANSWERS.md Q93-Q99 first.

## What lands (HUMAN_ANSWERS Q96, Q97 (2), Q98 (3))

I119 (b), whole. The opaque-arithmetic rule (I117's: the Go path enumerator's Reasoner reads an op or unop term as an
atom) becomes the Go frontend's default for every Go document, codec and machine, under every config version; the
narrow-arithmetic loop mode (I67) is unchanged. It is re-applied after the prereg commit by reverting I119's reverts:
cdd360b1 (which reverted ebdd14ca, the default flip, with its I117 P2 amendment) and 5587ebef (which reverted
ff9e463e, the three re-extracted Morph Go documents and I104's re-made Morph roles).

## The re-decision channel, by case (Q96 (1)). No verdict is carried across a change.

(a) Law file unchanged, decision inputs changed (model, evidence or facts read through its trace): the record is
re-made and re-decided on (b)'s tree. Where the law's binding cone changes, the binding moves through the
statement-diff log: model_extension (I83) when the model only gained behaviours, re-established by Bend and BendTT;
binding_change when the changed definitions are proven equal; otherwise the law is re-made and re-decided from scratch.

(b) Law file different only in `facts_sha256`: `reextraction` gains a **facts form** (build work, with planted
fixtures). An unsigned facts-form entry is accepted only when all hold: (1) the two law files are identical with
`facts_sha256` masked; (2) the new facts document is extractor output that its frontend reproduces byte for byte from
the pinned checkout, as G1 does, or a generated document whose every link to the pinned checkout is mechanical and
re-checked by the acceptance check itself (HUMAN_ANSWERS Q102: the generator in a generator closure reproduces it
from the document it names; each named document is extractor output G1 reproduces; every link's name and sha256
match; the chain is finite, acyclic and records each link's producer and version); (3) `facts_sha256` is that document's sha256; (4) `holon derive` reproduces the new law
from the same (rule, subform, basis) as HEAD's DERIVATION.json; (5) the record is re-decided on the new inputs. A
hand-written facts document never qualifies.

(c) The renumbered PAR law: the old id's verdict is retired, not transferred; the new id is a new law, decided fresh.
Counted, never named.

## Q56 for the re-decided records (Q96 (2), Q97 (2))

The re-decision runs in the builder's own sandbox, in the vault first, never in a CI re-make (CI output branches are
public). Nothing of (b) reaches the lead before it is complete. If no verdict changes among the affected records, the
re-made records are committed. If any verdict changes, in any direction, the builder sends the coordinator one line,
`I121 re-decision: <milestone>, <count> verdicts changed (PROVED and REFUTED together)`, and until the human's
disclosure call every affected law's committed record is withheld alike (UNKNOWN, with a reason naming I121 and Q56,
never its old status); the vault holds the re-decided records and a bundle commitment is committed. A new refutation
of Morph or corpus code keeps its witness in the vault, is replayed and classified, and, unless it is a model defect,
triggers `I121: potential vulnerability withheld, <system>, commitment <sha256>`. Q89 in every channel: a decided
count never says how it splits. Alerts are reported only in the outcome-independent form (Q101): every decided law
was handled under Q56 from the vault, and every alert the procedure called for was sent.

## F-M6-02 and the counted corpus run

F-M6-02 (M3's G1 with `--jobs` collides the fact directories): fixed if small, else it stays a ledger entry and M3's
G1 is not evidence. F-M6-03 is a known state: nothing is re-made for it.

One counted corpus run after the flip (Q98 (3)), aggregates only, labelled smoke on contaminated data (generality is
claimed only from I114's sealed pair). Its protocol, spec/M6/lib/i121_run.json, is the protocol of the last landing
before the run with only its doc changed: the flip is a default, not an opt-in, so it is the one change the run
measures. The counted-run rules hold (Q80, Q76, Q69); the preflight passes first; I103's toolchain sets are installed
and checked first; the coordinator gives the word on its base before it starts.

Predictions: spec/M6/predictions/I121.json. Tests: tests_m6/test_i121_re_decision.py.
