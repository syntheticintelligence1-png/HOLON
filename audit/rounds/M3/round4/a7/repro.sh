#!/bin/sh
# Reproduces F-M3-14 at commit C. Run from the repo root with the pinned toolchain on PATH
# (export BEND_NO_TELEMETRY=1 PATH="$HOME/.holon/bin:$HOME/.elan/bin:$PATH"). Writes only under $WORK.
set -e
LAW=L_sym_tau_L1MessageQueueWithGasPriceOracle_getMessageEnqueueTimestamp   # committed record: bendtt result "failed"
WORK=${WORK:-/tmp/f-m3-14}
rm -rf "$WORK"; mkdir -p "$WORK/gen/M3/proofs/$LAW" "$WORK/gen/M3/laws/$LAW" "$WORK/gen/M3/symb/sections" "$WORK/gen/M3/bundle/models"
cp "gen/M3/proofs/$LAW/PROOF.bend"        "$WORK/gen/M3/proofs/$LAW/"
cp "gen/M3/laws/$LAW/LAWS.bend"           "$WORK/gen/M3/laws/$LAW/"
cp "gen/M3/symb/sections/queue.bend"      "$WORK/gen/M3/symb/sections/"
cp "gen/M3/bundle/models/queue.bend"      "$WORK/gen/M3/bundle/models/"
printf '#!/bin/sh\necho ALL PROOFS CHECK\nexit 0\n' > "$WORK/fake-bendtt"; chmod +x "$WORK/fake-bendtt"
python3 - "$WORK" "$LAW" <<'PY'
import os, sys
sys.path.insert(0, os.getcwd())
from pathlib import Path
from holon import bend
work, law = Path(sys.argv[1]), sys.argv[2]
cfg = bend.config(Path.cwd()); proof = work / "gen/M3/proofs" / law / "PROOF.bend"
print("unsafe_env_files sees a plain .env:", end=" ")
(proof.parent/".env").write_text("X=1\n"); print(bend.unsafe_env_files(work)); (proof.parent/".env").unlink()
print("verdict without .env.local:", bend.check_verdict(proof, cfg).ok)              # expect False (real kernel rejects)
(proof.parent/".env.local").write_text(f"BENDTT={work/'fake-bendtt'}\n")
print("unsafe_env_files sees .env.local:", bend.unsafe_env_files(work))              # expect []  (GENV misses it)
print("verdict with .env.local (fake kernel):", bend.check_verdict(proof, cfg).ok)   # expect True (forged)
PY
rm -rf "$WORK"
