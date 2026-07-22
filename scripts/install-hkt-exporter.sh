#!/usr/bin/env bash
# Install / uninstall the HKT Prometheus exporter on macOS (host LaunchDaemon).
# Requires: public GitHub release access, sudo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_SRC="${REPO_ROOT}/speedx/com.hkt.hkt-prom-exporter.plist"
PLIST_DST="/Library/LaunchDaemons/com.hkt.hkt-prom-exporter.plist"
BIN_NAME="hkt-prom-exporter-darwin-arm64"
BIN_DST="/usr/local/bin/${BIN_NAME}"
RELEASE_URL="https://github.com/ipts-infrastructure/speedx/releases/latest/download/${BIN_NAME}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/install-hkt-exporter.sh [install]
  ./scripts/install-hkt-exporter.sh uninstall

Installs the HKT exporter binary to /usr/local/bin and enables the LaunchDaemon.
Requires macOS Apple Silicon (arm64) and sudo. GitHub release must be reachable (public).
EOF
}

require_macos_arm64() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "error: this installer only supports macOS" >&2
    exit 1
  fi
  if [[ "$(uname -m)" != "arm64" ]]; then
    echo "error: only darwin-arm64 binary is published; this machine is $(uname -m)" >&2
    exit 1
  fi
}

install_exporter() {
  require_macos_arm64

  if [[ ! -f "${PLIST_SRC}" ]]; then
    echo "error: missing plist at ${PLIST_SRC}" >&2
    exit 1
  fi

  local tmp
  tmp="$(mktemp -t hkt-prom-exporter.XXXXXX)"
  # shellcheck disable=SC2064
  trap "rm -f '${tmp}'" EXIT

  echo "Downloading ${BIN_NAME}..."
  curl -fL --retry 3 -o "${tmp}" "${RELEASE_URL}"
  chmod +x "${tmp}"

  echo "Installing binary to ${BIN_DST} (sudo)..."
  sudo mkdir -p /usr/local/bin
  sudo mv "${tmp}" "${BIN_DST}"
  trap - EXIT

  echo "Installing LaunchDaemon ${PLIST_DST} (sudo)..."
  sudo cp "${PLIST_SRC}" "${PLIST_DST}"
  sudo chown root:wheel "${PLIST_DST}"
  sudo chmod 644 "${PLIST_DST}"
  plutil -lint "${PLIST_DST}"

  # Reload if already loaded
  if sudo launchctl list 2>/dev/null | grep -q 'com.hkt.prom.exporter'; then
    sudo launchctl unload -w "${PLIST_DST}" 2>/dev/null || true
  fi
  sudo launchctl load -w "${PLIST_DST}"

  echo "Done. Metrics: http://localhost:28872/metrics"
}

uninstall_exporter() {
  require_macos_arm64

  if [[ -f "${PLIST_DST}" ]]; then
    echo "Unloading LaunchDaemon (sudo)..."
    sudo launchctl unload -w "${PLIST_DST}" 2>/dev/null || true
    sudo rm -f "${PLIST_DST}"
  else
    echo "LaunchDaemon not installed (${PLIST_DST})"
  fi

  if [[ -f "${BIN_DST}" ]]; then
    echo "Removing binary ${BIN_DST} (sudo)..."
    sudo rm -f "${BIN_DST}"
  else
    echo "Binary not installed (${BIN_DST})"
  fi

  echo "Uninstall complete."
}

cmd="${1:-install}"
case "${cmd}" in
  install) install_exporter ;;
  uninstall) uninstall_exporter ;;
  -h|--help|help) usage ;;
  *)
    echo "error: unknown command: ${cmd}" >&2
    usage >&2
    exit 1
    ;;
esac
