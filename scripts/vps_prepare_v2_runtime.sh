#!/usr/bin/env bash
set -Eeuo pipefail

release=""
release_link="/opt/alchemy-media-agent"
runtime_user="alchemy"
install_systemd=0

usage() {
  cat <<'USAGE'
Usage: scripts/vps_prepare_v2_runtime.sh --release PATH [--release-link PATH] [--runtime-user USER] [--install-systemd]

Creates or updates only the V2 virtual environment owned by the supplied
release, verifies declared dependencies, writes a release-bound runtime
manifest, and optionally installs the stable-link systemd templates.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release) release="$2"; shift 2 ;;
    --release-link) release_link="$2"; shift 2 ;;
    --runtime-user) runtime_user="$2"; shift 2 ;;
    --install-systemd) install_systemd=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

run_as_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "Root privileges are required for: $*" >&2
    exit 1
  fi
}

[[ -n "${release}" ]] || { usage >&2; exit 2; }
release="$(realpath "${release}")"
v2_dir="${release}/custom_media_agent_2_0"
venv_python="${v2_dir}/.venv/bin/python"
guard_source="${release}/ops/vps-release/v2_runtime_guard.py"

[[ -d "${v2_dir}" ]] || { echo "V2 directory is missing: ${v2_dir}" >&2; exit 1; }
[[ -f "${v2_dir}/requirements.txt" ]] || { echo "V2 requirements are missing." >&2; exit 1; }
[[ -f "${guard_source}" ]] || { echo "V2 runtime guard is missing." >&2; exit 1; }

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to prepare V2." >&2
  exit 1
fi

if [[ ! -x "${venv_python}" ]]; then
  python3 -m venv "${v2_dir}/.venv"
fi

"${venv_python}" -m pip install --disable-pip-version-check --no-input --upgrade-strategy only-if-needed -r "${v2_dir}/requirements.txt"
"${venv_python}" -m pip check
run_as_root chown -R "${runtime_user}:${runtime_user}" "${v2_dir}/.venv"
(cd "${v2_dir}" && "${venv_python}" -c 'import app.main; import httpx, httpcore')
run_as_root python3 "${guard_source}" --release "${release}" --write-manifest
run_as_root chown "${runtime_user}:${runtime_user}" "${v2_dir}/.alchemy-v2-runtime.json"
run_as_root python3 "${guard_source}" --release "${release}" --verify

if [[ "${install_systemd}" == "1" ]]; then
  install_root="/usr/local/lib/alchemy"
  run_as_root install -d -m 755 "${install_root}"
  run_as_root install -m 755 "${guard_source}" "${install_root}/v2_runtime_guard.py"
  for unit in alchemy-v2-api.service alchemy-v2-worker.service alchemy-v2-sync-worker.service; do
    template="${v2_dir}/deploy/systemd/${unit}"
    [[ -f "${template}" ]] || { echo "Systemd template is missing: ${template}" >&2; exit 1; }
    sed "s|__ALCHEMY_RELEASE_LINK__|${release_link}|g" "${template}" | run_as_root tee "/etc/systemd/system/${unit}" >/dev/null
  done
  run_as_root systemctl daemon-reload
fi

echo "V2_RUNTIME_PREPARED_RELEASE=${release}"
echo "V2_RUNTIME_REQUIREMENTS_SHA256=$(sha256sum "${v2_dir}/requirements.txt" | awk '{print $1}')"
