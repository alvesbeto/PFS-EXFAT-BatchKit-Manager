#!/usr/bin/env bash
# Build pfs-batchkit one-file executables with PyInstaller (run on each target OS).
#
# Dev rápido (sem reempacotar Qt): pip install -e ".[gui]" && pfs-batchkit-ui
#
# Uso:
#   ./packaging/build.sh              # CLI + GUI, incremental (sem --clean)
#   ./packaging/build.sh --fast       # só GUI (PySide6 demora; CLI usa pip/venv)
#   ./packaging/build.sh --cli-only   # só pfs-batchkit (~1 min)
#   ./packaging/build.sh --gui-only   # só pfs-batchkit-ui
#   ./packaging/build.sh --clean      # rebuild completo (lento)
#   ./packaging/build.sh --parallel   # CLI e GUI em paralelo
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

BUILD_CLI=1
BUILD_GUI=1
PYI_CLEAN=""
PARALLEL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cli-only) BUILD_GUI=0 ;;
    --gui-only) BUILD_CLI=0 ;;
    --fast) BUILD_CLI=0 ;;
    --clean) PYI_CLEAN="--clean" ;;
    --parallel) PARALLEL=1 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Opção desconhecida: $1 (use --help)" >&2
      exit 2
      ;;
  esac
  shift
done

PY="${ROOT}/.venv/bin/python3"
if [[ ! -x "${PY}" ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv "${ROOT}/.venv"
    uv pip install --python "${PY}" -e "${ROOT}[build,gui]"
  elif python3 -c "import PyInstaller" 2>/dev/null; then
    PY="python3"
  else
    echo "Install deps: uv venv + uv pip install -e '.[build,gui]' OR pip install pyinstaller" >&2
    exit 1
  fi
fi

if ! "${PY}" -c "import PyInstaller" 2>/dev/null; then
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "${PY}" -e "${ROOT}[build,gui]"
  else
    echo "PyInstaller missing on ${PY}" >&2
    exit 1
  fi
fi

OUT="${ROOT}/dist"
mkdir -p "${OUT}"

run_pyinstaller() {
  local spec="$1"
  echo "==> PyInstaller ${spec}${PYI_CLEAN:+ (clean)}"
  "${PY}" -m PyInstaller "${ROOT}/packaging/${spec}" --noconfirm ${PYI_CLEAN:+"$PYI_CLEAN"}
}

if [[ "${PARALLEL}" -eq 1 ]] && [[ "${BUILD_CLI}" -eq 1 ]] && [[ "${BUILD_GUI}" -eq 1 ]]; then
  run_pyinstaller pfs-batchkit.spec &
  pid_cli=$!
  run_pyinstaller pfs-batchkit-ui.spec &
  pid_gui=$!
  wait "${pid_cli}" "${pid_gui}"
else
  [[ "${BUILD_CLI}" -eq 1 ]] && run_pyinstaller pfs-batchkit.spec
  [[ "${BUILD_GUI}" -eq 1 ]] && run_pyinstaller pfs-batchkit-ui.spec
fi

PFSSHELL="${ROOT}/tools/bin/pfsshell"
if [[ -x "${PFSSHELL}" ]]; then
  install -m755 "${PFSSHELL}" "${OUT}/pfsshell"
fi

echo "Binaries in ${OUT}/"
ls -la "${OUT}/"
