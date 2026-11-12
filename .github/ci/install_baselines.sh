#!/usr/bin/env bash
# I52 only (not run by CI's toolchain job): install the pinned baseline tools of config/holon.json "baselines" under
# ~/.holon/tools. Every download is checked against its sha256; the Python tools come from the pinned requirements file.
# hevm/cvc5 and Go are the existing toolchain pins (install_toolchain.sh). A tool whose pin cannot be met is reported,
# and the run records it as missing (config baselines.tools.<name>.missing), never substituted.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
T="$HOME/.holon/tools"
cfg() { python3 -c "import json,sys; d=json.load(open('$REPO/config/holon.json'))['baselines']['tools']
for k in sys.argv[1].split('.'): d=d[k]
print(d)" "$1"; }
sha_ok() { local got; got="$(sha256sum "$1" | cut -d' ' -f1)"; [ "$got" = "$2" ] || { echo "SHA MISMATCH $1: got $got want $2" >&2; exit 1; }; echo "sha256 ok $1"; }
mkdir -p "$T/dl"
for tool in echidna medusa; do
  v="$(cfg $tool.version)"; url="$(cfg $tool.url)"; a="$T/dl/$(basename "$url")"
  curl -sSfL --retry 5 -o "$a" "$url"; sha_ok "$a" "$(cfg $tool.archive_sha256)"
  mkdir -p "$T/$tool-$v"; tar -xzf "$a" -C "$T/$tool-$v"; sha_ok "$(cfg $tool.path)" "$(cfg $tool.sha256)"
done
python3 -m venv "$T/baselines-py"
"$T/baselines-py/bin/pip" install -q --no-deps -r "$REPO/config/baselines_requirements.txt"
"$T/baselines-py/bin/pip" freeze --all | sort | cmp - "$REPO/config/baselines_requirements.txt"
GOTOOLCHAIN=local go build -o "$T/i52-gotool" "$REPO/holon/eval/baselines/gotool/main.go"
