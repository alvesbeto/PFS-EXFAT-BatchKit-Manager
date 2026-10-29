#!/usr/bin/env bash
# Build pfsshell with mkfs command (tools/pfsshell-mkfs.patch) into tools/bin/pfsshell
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${ROOT}/tools/pfsshell-build"
BIN="${ROOT}/tools/bin/pfsshell"
PATCH="${ROOT}/tools/pfsshell-mkfs.patch"
FLATPAK_SDK="${PFS_BATCHKIT_FLATPAK_SDK:-org.freedesktop.Sdk//24.08}"

mkdir -p "${ROOT}/tools/bin"

if [[ -x "${BIN}" ]] && printf 'help\nexit\n' | "${BIN}" 2>&1 | grep -q 'mkfs <part_name>'; then
  echo "Already built with mkfs: ${BIN}"
  exit 0
fi

_build_inner() {
  if [[ ! -d "${BUILD_DIR}/.git" ]]; then
    git clone --recursive --depth 1 https://github.com/ps2homebrew/pfsshell.git "${BUILD_DIR}"
  fi
  cd "${BUILD_DIR}"
  git submodule update --init --recursive
  if patch -p1 --forward --dry-run < "${PATCH}" >/dev/null 2>&1; then
    patch -p1 --forward < "${PATCH}"
  fi
  meson setup build --prefix="${ROOT}/tools" 2>/dev/null || meson setup build --prefix="${ROOT}/tools" --reconfigure
  meson compile -C build pfsshell
  install -m755 build/pfsshell "${BIN}"
  echo "Installed ${BIN}"
}

if command -v meson >/dev/null 2>&1 && command -v ninja >/dev/null 2>&1; then
  _build_inner
elif command -v flatpak >/dev/null 2>&1 && flatpak info "${FLATPAK_SDK}" >/dev/null 2>&1; then
  flatpak run --share=network --filesystem="${ROOT}" --command=bash "${FLATPAK_SDK}" -c "set -e; $(typeset -f _build_inner); _build_inner"
else
  echo "Install meson+ninja, or Flatpak SDK (${FLATPAK_SDK})." >&2
  exit 1
fi
