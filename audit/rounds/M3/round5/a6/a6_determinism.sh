#!/bin/bash
# A6: regenerate chosen generated files twice from the scratch tree $T of the target commit, into separate output
# directories, and compare the two runs with each other and with the committed files. Usage: a6_determinism.sh T OUT
set -u
T=$1; O=$2
mkdir -p "$O"
cd "$T"
export BEND_NO_TELEMETRY=1 PATH="$HOME/.holon/bin:$HOME/.elan/bin:$PATH" TMPDIR=/tmp/audit-m3-r5/tmp
unset BUN_OPTIONS
for i in 1 2; do
  python -m holon codecs --milestone M3 --root "$T" --out "$O/r$i/codec" --goops-out "$O/r$i/goops" > "$O/codecs_$i.log" 2>&1; echo "codecs run $i exit $?"
  python -m holon own --milestone M3 --root "$T" --out "$O/r$i/own" > "$O/own_$i.log" 2>&1; echo "own run $i exit $?"
  python -m holon derive --milestone M3 --root "$T" --out "$O/r$i/laws" --obstructions "$O/r$i/obstructions.json" > "$O/derive_$i.log" 2>&1; echo "derive run $i exit $?"
  python -m holon backtest --milestone M3 --root "$T" --out "$O/r$i/backtest.json" > "$O/backtest_$i.log" 2>&1; echo "backtest run $i exit $?"
  python -m holon extract solidity --root "$T" --sidecar spec/M2/lib/extract_rollup.json --source /root/work/morph --out "$O/r$i/morph_rollup.extracted.json" > "$O/extract_$i.log" 2>&1; echo "extract run $i exit $?"
done
echo "--- run 1 vs run 2"
diff -r "$O/r1" "$O/r2" > "$O/r1_vs_r2.diff" 2>&1 && echo "IDENTICAL r1 r2" || echo "DIFFER r1 r2 ($(wc -l < "$O/r1_vs_r2.diff") diff lines)"
echo "--- run 1 vs committed"
for pair in "codec:gen/M3/codec" "goops:gen/M3/goops" "own:gen/M3/own"; do
  a=${pair%%:*}; b=${pair#*:}
  diff -r "$O/r1/$a" "$T/$b" > "$O/r1_vs_committed_$a.diff" 2>&1 && echo "IDENTICAL $a $b" || echo "DIFFER $a $b ($(wc -l < "$O/r1_vs_committed_$a.diff") lines)"
done
for f in $(cd "$O/r1/laws" && ls); do
  cmp -s "$O/r1/laws/$f" "$T/laws/M3/$f" || echo "DIFFER laws/M3/$f"
done
echo "laws files: $(ls "$O/r1/laws" | wc -l) regenerated, $(ls "$T/laws/M3" | wc -l) committed"
cmp -s "$O/r1/obstructions.json" "$T/gen/M3/sorts/obstructions.json" && echo "IDENTICAL obstructions.json" || echo "DIFFER obstructions.json"
cmp -s "$O/r1/backtest.json" "$T/results/M3/backtest.json" && echo "IDENTICAL backtest.json" || echo "DIFFER backtest.json"
cmp -s "$O/r1/morph_rollup.extracted.json" "$T/spec/M2/facts/morph_rollup.extracted.json" && echo "IDENTICAL morph_rollup.extracted.json" || echo "DIFFER morph_rollup.extracted.json"
