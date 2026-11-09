#!/bin/bash
# A7: G9 on the scratch tree $T of the target commit as committed, then after emptying the premises of one record
# whose law has assume clauses and whose record lists them. Usage: a7_g9.sh T OUT
set -u
T=$1; O=$2; mkdir -p "$O"
cd "$T"
export BEND_NO_TELEMETRY=1 PATH="$HOME/.holon/bin:$HOME/.elan/bin:$PATH" TMPDIR=/tmp/audit-m3-r5/tmp
unset BUN_OPTIONS
python -m holon gate --milestone M3 --root "$T" --checks G9 --report "$O/g9_committed.json" > "$O/g9_committed.log" 2>&1; echo "G9 as committed: exit $?"
python3 - "$O/g9_committed.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1])); c = r["checks"]["G9"]
print("  G9 passed:", c["passed"], "|", c["detail"][:200])
PY
L=L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned
cp "results/M3/$L.json" "$O/$L.orig.json"
python3 - "results/M3/$L.json" "laws/M3/$L.json" <<'PY'
import json, sys
p, lp = sys.argv[1], sys.argv[2]
r = json.load(open(p)); law = json.load(open(lp))
print("  tamper:", len(law["statement"]["assume"]), "assume clauses;", len(r["premises"]), "premises listed -> 0")
r["premises"] = []
open(p, "w").write(json.dumps(r, indent=1, sort_keys=True) + "\n")
PY
python -m holon gate --milestone M3 --root "$T" --checks G9 --report "$O/g9_tampered.json" > "$O/g9_tampered.log" 2>&1; echo "G9 after the tamper: exit $?"
python3 - "$O/g9_tampered.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1])); c = r["checks"]["G9"]
print("  G9 passed:", c["passed"], "|", c["detail"][:200])
PY
cp "$O/$L.orig.json" "results/M3/$L.json"
echo "restored results/M3/$L.json"
