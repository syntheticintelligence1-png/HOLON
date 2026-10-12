# I11: diagram 𝔇 and principal classes

Rendered from `docs/BUILD_PLAN.md` §4, I11 (whitepaper §4 Defs 4.1–4.4 and 4.7, §8.3).

## What to build

- **`holon/diagram/`:**
  - `model.py`: `Carrier`, `Edge`, `Diagram`;
  - `build.py`: adapters, one mapping per facts section;
  - `access.py`: read/write sets with index terms;
  - `principals.py`: principal classes.
- **`python -m holon diagram --milestone M2 [--out DIR]`** writes `gen/M2/diagram/<model>.json` for every fact document:
  - `facts/morph_header.json`;
  - `spec/M1/facts/morph_rollup.json`;
  - `spec/M1/facts/morph_batchdata.json`.
- **`spec/schemas/diagram.schema.json`.**
- **Mapping.** Every top-level facts section is mapped and listed in `mapped_sections`; zero unmapped constructs.
  - Facts 0.1:
    - `types` → base types;
    - `functions` → CODEC edges (the decoder is partial; projections are product metadata, not edges); the predicates `ok_*` become domains of the `Bytes` interface carrier;
    - `assumptions` → ledger links.
  - Facts 0.2:
    - `state` → a STORE/LOAD pair per field;
    - `actions` → TRANS. `wait` is the environment edge (`env: true`). Index-sensitive reads/writes appear as `index_terms`, rendered `[field, term]` with infix terms and no spaces: `["win", "idx-lfi"]`, `["chs", "bc"]`, the shadow slot `["s_csr", "lci+1"]`.
    - `migrations` → MIG; `legacy` is a pseudo-migration (`pseudo: true`);
    - `consumers` → CONS;
    - `observers` → observation LOAD edges;
    - `principals` → principal classes `{owner, active_submitter, challenger, anyone, environment}`, each with a permission predicate taken from the actions' guards;
    - `params`, `constants_doc`, `types`, `ghost_state`, `shadow`, `initial`, `reasons`, `defs`, `disch`, `coverage`, `abstractions`, `target`, `extraction`, `policy`, `search` → carriers or metadata as named in the plan.
  - 0 HASH edges in M1 facts, recorded as coverage debt.

## Rules

- Deterministic output: sorted keys and stable ids.
- A construct that fits no edge kind is a question for the human, not a forced mapping.
