# holon/ — the M0 factory package (stdlib only, Python >= 3.10)

Module -> spec map:

| Module | M0_SPEC | Role |
|---|---|---|
| `facts.py` | section 3-4 | load facts, facts sha256, Header widths, `when` evaluation |
| `ir.py` | section 3 | canonical JSON, statement hashes, law/registry loading |
| `layout.py` | section 5 | symbolic byte layout of an encoder (`["field",n,k]` / `["const",v]` / `["unknown"]`) |
| `gen_model.py` | section 4, BEND_PRIMER 5.1 | facts -> `morph_header.bend` (one U32 per byte; dirty EVM memory = 57005) |
| `model_eval.py` | section 5 | compile the model (`bend -o model.mjs`) and evaluate it in node; `eval_batch`, `eval_claim` |
| `emit.py` | section 6, BEND_PRIMER 5.2-5.4 | law IR -> `LAWS.bend`/`PROOF.bend` (pins, refl_after_open, exs counter-laws) |
| `refute.py` | section 6 | deterministic bounded witness search on the compiled model |
| `run.py` | section 6 | the pipeline: proof attempt -> refutation -> result records + `summary.json` |
| `gate.py` | section 7 | GENV, G2, G1, G3, G5, G11, G4 (canaries) -> `gate_report.json` |
| `__main__.py` | section 5 | CLI: `python -m holon run|gate --milestone M0` |

Rules honoured here: no model logic in Python (witnesses are evaluated on the
compiled Bend model via `model_eval`), no imports from `tests/`, generated
files are byte-identical across runs, no `bunfig.toml`/`.env` anywhere.
