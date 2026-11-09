#!/bin/bash
# A1 follow-up for m11: does the bundle's own extraction (holon bundle extract, which writes the member documents) see
# the m11 mutation? A scratch clone of the pinned checkout gets the m11 edit (git told to treat the file as unchanged,
# as holon audit mutation does), the scratch tree's config names the clone, and `holon bundle extract --check` compares
# a fresh build with the committed documents, writing nothing. Usage: m11_bundle_check.sh T OUT
set -u
T=$1; O=$2; mkdir -p "$O"
SRC=/tmp/audit-m3-r5/m11src
rm -rf "$SRC"
git clone -q --shared --no-checkout /root/work/morph "$SRC" && git -C "$SRC" checkout -q --detach 3e44e795586af3e11285b603ab642c67823add51
F=contracts/contracts/l1/L1CrossDomainMessenger.sol
python3 - "$SRC/$F" <<'PY'
import sys
p = sys.argv[1]; L = open(p).read().splitlines(keepends=True)
old = "estimateCrossDomainMessageFee(_msgSender(), _gasLimit)"
assert L[289].count(old) == 1, L[289]
L[289] = L[289].replace(old, "estimateCrossDomainMessageFee(_to, _gasLimit)")
open(p, "w").write("".join(L))
PY
git -C "$SRC" update-index --assume-unchanged -- "$F"
git -C "$SRC" diff --stat; git -C "$SRC" status --porcelain --untracked-files=no | head -3
cp "$T/config/holon.json" "$O/holon.json.orig"
python3 - "$T/config/holon.json" "$SRC" <<'PY'
import json, sys
p, src = sys.argv[1], sys.argv[2]
c = json.load(open(p)); c["extract"]["sources"]["morph-l2/morph"] = src
open(p, "w").write(json.dumps(c, indent=2) + "\n")
PY
cd "$T"
export BEND_NO_TELEMETRY=1 PATH="$HOME/.holon/bin:$HOME/.elan/bin:$PATH" TMPDIR=/tmp/audit-m3-r5/tmp
unset BUN_OPTIONS
python -m holon bundle extract --milestone M3 --root "$T" --check > "$O/bundle_extract_check_mutant.log" 2>&1; echo "bundle extract --check on the m11 mutant: exit $?"
tail -3 "$O/bundle_extract_check_mutant.log"
cp -r "$T/gen/M3/bundle" "$O/bundle_committed"
python -m holon bundle extract --milestone M3 --root "$T" > "$O/bundle_extract_mutant.log" 2>&1; echo "bundle extract on the m11 mutant (writes the scratch tree): exit $?"
tail -3 "$O/bundle_extract_mutant.log"
diff <(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); d.get('extraction',{}).pop('inputs',None); print(json.dumps(d,indent=1,sort_keys=True))" "$O/bundle_committed/documents/messenger.json") <(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); d.get('extraction',{}).pop('inputs',None); print(json.dumps(d,indent=1,sort_keys=True))" "$T/gen/M3/bundle/documents/messenger.json") > "$O/messenger_document.diff"; echo "messenger document content diff (inputs' hashes aside): $(wc -l < "$O/messenger_document.diff") lines"
head -40 "$O/messenger_document.diff"
rm -rf "$T/gen/M3/bundle" && cp -r "$O/bundle_committed" "$T/gen/M3/bundle" && rm -rf "$O/bundle_committed"
cp "$O/holon.json.orig" "$T/config/holon.json"
diff -r "$T/gen/M3/bundle" /home/user/audit-m3-r5/gen/M3/bundle > /dev/null && echo "scratch tree's gen/M3/bundle restored to C" || echo "RESTORE MISMATCH"
cmp -s "$T/config/holon.json" /home/user/audit-m3-r5/config/holon.json && echo "config restored to C"
rm -rf "$SRC"
