#!/bin/sh
# Installs claudebar for the current user (no root): the prebuilt binary for this
# machine, or a build from source when there is none.
#   curl -fsSL https://raw.githubusercontent.com/mkalmousli/ClaudeStatusBar/main/install.sh | sh
set -eu
REPO=mkalmousli/ClaudeStatusBar
die() { echo "claudebar: $*" >&2; exit 1; }

case $(uname -s) in
  Linux) os=linux ;; Darwin) os=macos ;; FreeBSD) os=freebsd ;;
  *) die "unsupported system $(uname -s) (Linux, macOS and FreeBSD only; on Windows use WSL)" ;;
esac
case $(uname -m) in
  x86_64|amd64) arch=x86_64 ;; aarch64|arm64) arch=aarch64 ;; armv7*|armv8l) arch=armv7 ;;
  i386|i686) arch=i686 ;; riscv64) arch=riscv64 ;; ppc64le) arch=ppc64le ;; s390x) arch=s390x ;;
  *) arch=unknown ;;
esac

dl() { if command -v curl >/dev/null 2>&1; then curl -fsSL -o "$2" "$1"; else wget -qO "$2" "$1"; fi; }
sum() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
name=claudebar-$os-$arch
base=https://github.com/$REPO/releases/latest/download

if dl "$base/$name" "$tmp/claudebar" 2>/dev/null && dl "$base/$name.sha256" "$tmp/sum" 2>/dev/null \
   && [ "$(cut -d' ' -f1 "$tmp/sum")" = "$(sum "$tmp/claudebar" | cut -d' ' -f1)" ]; then
  echo "downloaded $name"
else
  echo "no usable prebuilt binary for $os-$arch, building from source"
  command -v git >/dev/null 2>&1 && command -v cc >/dev/null 2>&1 || die "building needs git and a C compiler (cc)"
  git clone -q --depth 1 "https://github.com/$REPO" "$tmp/src"
  (cd "$tmp/src" && cc build.c -o build && OUT="$tmp/out" ./build) || die "build failed"
  cp "$tmp/out/claudebar" "$tmp/claudebar"
fi
# The GUI is optional (needs GTK3): fetch it when this machine has GTK3 and a release has it.
if ldconfig -p 2>/dev/null | grep -q libgtk-3.so.0 && dl "$base/claudebar-gui-$os-$arch" "$tmp/claudebar-gui" 2>/dev/null \
   && dl "$base/claudebar-gui-$os-$arch.sha256" "$tmp/gsum" 2>/dev/null \
   && [ "$(cut -d' ' -f1 "$tmp/gsum")" = "$(sum "$tmp/claudebar-gui" | cut -d' ' -f1)" ]; then
  chmod +x "$tmp/claudebar-gui"
else
  rm -f "$tmp/claudebar-gui"
fi
[ -f "$tmp/out/claudebar-gui" ] && cp "$tmp/out/claudebar-gui" "$tmp/claudebar-gui"
chmod +x "$tmp/claudebar"
"$tmp/claudebar" install
