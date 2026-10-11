# Session P1: law IR and layout algebra (about 1–2 hours)

Read `AGENTS.md`, `docs/M0_SPEC.md` (§3–§5) and `docs/BEND_NOTES.md`.

The frozen digest is `f854d69b0b58b581eb205a657d6925cc1e1460141ef9626df89ea87de1594fd0`. Check it before you start and again before you open the PR.

## Tasks

Create the Python package `holon/` (stdlib only, Python ≥ 3.10):

- `holon/__init__.py`, and `holon/__main__.py` (CLI entry; subcommands can be stubs for now).
- `holon/facts.py`: load facts and compute the facts sha256.
- `holon/ir.py`: `canonical_json`, `statement_hash`, `load_laws(milestone="M0", root=None)`, exactly as M0_SPEC §3 defines them.
- `holon/layout.py`: `layout(facts, fn, version)`, the symbolic byte layout of an encoder.
  - EVM memory starts as `["unknown"]`; Go buffers start as `["const", 0]`.
  - Later writes override earlier ones.
  - `when` conditions apply.
  - Memory is at least the output length.
  - Write it from the spec. Do not copy `tests/reference/`.

## Definition of done

- This passes:
  ```
  python -m unittest tests.test_10_layout tests.test_11_ir tests.test_12_hygiene -v
  ```
- So do tests 00–02.
- Add a short `holon/README.md` that maps modules to spec sections.
