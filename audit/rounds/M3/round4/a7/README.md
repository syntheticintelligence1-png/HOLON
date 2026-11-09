A7 (gate_evasion) evidence: GENV's unsafe-Bun-config scan (holon.bend.unsafe_env_files) blocks only the exact
filenames `bunfig.toml` and `.env`, but bun loads `.env.local` (and `.env.<NODE_ENV>`) from the checker's working
directory. The checker runs with cwd = the proof directory (holon.bend.run uses cwd=proof_file.parent). A committed
`.env.local` in a proof directory therefore reaches the checker. holon.bend._env() pops BENDTT/BEND_LIB/BEND_HUB/
BUN_OPTIONS from the *Python* process environment, and GENV refuses a BENDTT set in the Python process, but neither
stops bun from re-reading BENDTT/BEND_LIB from `.env.local` inside the checker process.

a7_envlocal.py (run with PATH to the pinned toolchain) uses a minimal scratch copy of one committed REFUTED law whose
recorded bendtt result is "failed" (the pinned BendTT kernel rejects its counter-law). It shows:
  - holon.bend.check_verdict on the committed PROOF.bend returns ok=False (SOME PROOFS FAIL) with no `.env.local`;
  - with `.env.local` = "BENDTT=<fake kernel that prints ALL PROOFS CHECK>" written beside the proof, check_verdict
    returns ok=True (ALL PROOFS CHECK) and the fake kernel's log records the invocation;
  - holon.bend.unsafe_env_files returns [] for `.env.local` and `.env.development` (GENV misses them), and [the file]
    only for a plain `.env`.

check_verdict is the second kernel used by G7 (dual-kernel), G11V (inhabitant dual-check) and the record writer
(records.kernels -> bendtt result, independence_class). So a committed `.env.local` forges the second-kernel verdict.

Corroboration in the tree: holon/consumers.py NO_BUN_CONFIG = shutil.ignore_patterns(".env", ".env.*", "bunfig.toml")
strips ALL `.env*` variants when copying scratch trees, citing AGENTS.md rule 8; GENV's enforcement does not match
`.env.*`.
