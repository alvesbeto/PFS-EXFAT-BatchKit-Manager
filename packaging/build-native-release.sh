#!/usr/bin/env bash
# Build native binaries on this machine and stage under dist/releases/<platform-id>/.
# PyInstaller cannot cross-compile: Linux/macOS/Windows builds require each OS (use GitHub Actions).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

case "$(uname -s)" in
  Linux)  PLATFORM_ID="linux-$(uname -m)" ;;
  Darwin) PLATFORM_ID="macos-$(uname -m)" ;;
  MINGW*|MSYS*|CYGWIN*) PLATFORM_ID="windows-$(uname -m)" ;;
  *)      PLATFORM_ID="unknown-$(uname -s)-$(uname -m)" ;;
esac

"${ROOT}/packaging/build.sh"

RELEASE_DIR="${ROOT}/dist/releases/${PLATFORM_ID}"
mkdir -p "${RELEASE_DIR}"
shopt -s nullglob
for f in "${ROOT}/dist/pfs-batchkit"* "${ROOT}/dist/pfsshell"*; do
  [[ -e "$f" ]] || continue
  base="$(basename "$f")"
  cp -f "$f" "${RELEASE_DIR}/${base}"
done

echo ""
echo "Native build staged: ${RELEASE_DIR}"
ls -la "${RELEASE_DIR}"

if [[ "${PLATFORM_ID}" != linux-* ]]; then
  echo ""
  echo "Other platforms: push this repo to GitHub and run workflow 'Build' (workflow_dispatch)"
  echo "  or open Actions after push to main — artifacts: pfs-batchkit-linux-x86_64, macos-arm64, windows-x86_64"
fi
