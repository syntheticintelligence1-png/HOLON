#!/usr/bin/env bash
# The I103 toolchain sets (config/toolchains.json solc_set and go_set), next to the CI pins, which this script never
# touches. Every binary is checked against its pinned sha256; a mismatch stops the script.
#   solc_set: <solc_set.dir>/solc-<version>   (binaries.soliditylang.org linux-amd64 static builds)
#   go_set:   <goroot> of every release with a url (go.dev tarballs); 1.24.7 is replay.go_version's toolchain (CI's
#             setup-go, /usr/local/go here) and is only checked, never downloaded.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
python3 - "$REPO/config/toolchains.json" > "$TMP/plan" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))
s = c["solc_set"]
for v, sha in sorted(s["releases"].items()):
    print("solc", v, sha, s["dir"] + "/solc-" + v, s["url"].replace("{version}", v).replace("{build}", s["builds"][v]))
for v, r in sorted(c["go_set"]["releases"].items()):
    if r.get("url"):
        print("go", v, r["sha256"], r["goroot"], r["url"])
PY
fetch() { curl -sSfL --retry 5 --retry-delay 5 -o "$1" "$2"; }
check() { local got; got="$(sha256sum "$1" | cut -d' ' -f1)"; [ "$got" = "$2" ] || { echo "SHA MISMATCH $1: $got want $2" >&2; exit 1; }; }
while read -r kind v sha dest url; do
  if [ "$kind" = solc ]; then
    if [ -f "$dest" ] && [ "$(sha256sum "$dest" | cut -d' ' -f1)" = "$sha" ]; then continue; fi
    mkdir -p "$(dirname "$dest")"; fetch "$TMP/solc" "$url"; check "$TMP/solc" "$sha"
    install -m 0755 "$TMP/solc" "$dest"; echo "solc $v ok"
  else
    if [ -x "$dest/bin/go" ]; then continue; fi
    fetch "$TMP/go.tgz" "$url"; check "$TMP/go.tgz" "$sha"
    mkdir -p "$TMP/go-$v"; tar -xzf "$TMP/go.tgz" -C "$TMP/go-$v"
    mkdir -p "$(dirname "$dest")"; rm -rf "$dest"; mv "$TMP/go-$v/go" "$dest"; echo "go $v ok"
  fi
done < "$TMP/plan"
