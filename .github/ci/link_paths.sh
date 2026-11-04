#!/usr/bin/env bash
# CI only: config/holon.json names absolute /root/... paths (replay, extract, hevm). On the runner the
# tools live under $HOME; link the configured paths to them instead of editing the config.
set -euo pipefail
mkdir -p "$HOME/.holon" "$HOME/holon-work"
sudo chmod o+x /root
sudo ln -sfn "$HOME/.holon" /root/.holon
sudo ln -sfn "$HOME/holon-work" /root/work
ls -ld /root/.holon /root/work
# the bend wrapper (tools/install_bend.sh) is found as `bend`, as config bend.cmd expects
if [ -n "${GITHUB_PATH:-}" ]; then echo "$HOME/.holon/bin" >> "$GITHUB_PATH"; fi
