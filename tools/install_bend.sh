#!/usr/bin/env bash
# Install Bend 2 pinned to the commit the probes were verified with, plus a `bend` wrapper.
#   tools/install_bend.sh [PREFIX]      (default PREFIX=$HOME/.holon)
# Alternative: the official installer (latest release):  curl -fsSL https://bend-lang.com/install.sh | sh
set -euo pipefail
PIN_COMMIT="2343aec043b7967f2a6f653e7f2e3bcbe55c8c9a"   # bend 2.0.36, 2026-10-10
PREFIX="${1:-$HOME/.holon}"
mkdir -p "$PREFIX/bin"
if ! command -v bun >/dev/null 2>&1 && [ ! -x "$HOME/.bun/bin/bun" ]; then
  echo "installing bun (https://bun.sh)"; curl -fsSL https://bun.sh/install | bash
fi
BUN="$(command -v bun || echo "$HOME/.bun/bin/bun")"
if [ ! -d "$PREFIX/bend/.git" ]; then
  git clone https://github.com/bendlang/bend "$PREFIX/bend"
fi
git -C "$PREFIX/bend" fetch --quiet origin "$PIN_COMMIT" || git -C "$PREFIX/bend" fetch --quiet origin
git -C "$PREFIX/bend" checkout --quiet "$PIN_COMMIT"
cat > "$PREFIX/bin/bend" <<WRAP
#!/bin/sh
exec "$BUN" "$PREFIX/bend/bend2/main.ts" "\$@"
WRAP
chmod +x "$PREFIX/bin/bend"
"$PREFIX/bin/bend" version
echo "add to PATH:  export PATH=\"$PREFIX/bin:\$PATH\""
echo "or set config/holon.json bend.cmd to [\"$PREFIX/bin/bend\"]"
echo "NOTE: this runner reads bunfig.toml/.env from the working directory; keep them out of the repo."
