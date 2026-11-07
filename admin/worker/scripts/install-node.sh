#!/bin/sh
# Node.js 22 for the current user, no sudo: the latest v22 from nodejs.org,
# checked against its SHASUMS256.txt, unpacked to ~/.local/node, and
# node/npm/npx linked into ~/.local/bin (put on the login PATH via ~/.profile).
# Does nothing when a node >= 22 is already on PATH.
#
#   sh worker/scripts/install-node.sh
set -eu
need=22
if command -v node >/dev/null 2>&1; then
  have=$(node -p 'process.versions.node.split(".")[0]')
  if [ "$have" -ge "$need" ]; then echo "node $(node -v) is already on PATH — nothing to do"; exit 0; fi
fi
case "$(uname -s)" in Linux) os=linux ;; Darwin) os=darwin ;; *) echo "unsupported OS: $(uname -s)" >&2; exit 1 ;; esac
case "$(uname -m)" in x86_64|amd64) arch=x64 ;; aarch64|arm64) arch=arm64 ;; *) echo "unsupported CPU: $(uname -m)" >&2; exit 1 ;; esac
base=https://nodejs.org/dist/latest-v$need.x
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
curl -fsSL "$base/SHASUMS256.txt" -o "$tmp/SHASUMS256.txt"
file=$(awk -v s="-$os-$arch.tar.gz" 'index($2, s) && $2 ~ /^node-v/ {print $2}' "$tmp/SHASUMS256.txt" | head -1)
[ -n "$file" ] || { echo "no $os-$arch build in $base" >&2; exit 1; }
curl -fsSL "$base/$file" -o "$tmp/$file"
(cd "$tmp" && grep " $file\$" SHASUMS256.txt | sha256sum -c - >/dev/null 2>&1 || grep " $file\$" SHASUMS256.txt | shasum -a 256 -c - >/dev/null) \
  || { echo "checksum mismatch for $file" >&2; exit 1; }
dir=${file%.tar.gz}
mkdir -p "$HOME/.local/bin"
rm -rf "$HOME/.local/$dir"
tar -xzf "$tmp/$file" -C "$HOME/.local"
ln -sfn "$HOME/.local/$dir" "$HOME/.local/node"
for b in node npm npx; do
  if [ -e "$HOME/.local/bin/$b" ] && [ ! -L "$HOME/.local/bin/$b" ]; then echo "~/.local/bin/$b exists and is not a link — left alone" >&2; continue; fi
  ln -sfn "$HOME/.local/node/bin/$b" "$HOME/.local/bin/$b"
done
grep -qs '.local/bin' "$HOME/.profile" || printf '\n# mentat-admin: node/npm/npx live in ~/.local/bin\n[ -d "$HOME/.local/bin" ] && PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME/.profile"
echo "installed $("$HOME/.local/node/bin/node" -v) in ~/.local/node; new login shells find it."
echo "In THIS shell run:  export PATH=\"\$HOME/.local/bin:\$PATH\""
