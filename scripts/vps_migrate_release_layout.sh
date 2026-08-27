#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${REPO_URL:-https://github.com/meta-xucong/alchemy-media-agent.git}"
TARGET_SHA="${TARGET_SHA:?TARGET_SHA must be a full commit SHA}"
DEPLOY_LINK="${DEPLOY_LINK:-/opt/alchemy-media-agent}"
RELEASE_ROOT="${RELEASE_ROOT:-/opt/alchemy-media-agent-releases}"
REPOSITORY_ROOT="${REPOSITORY_ROOT:-/opt/alchemy-media-agent-repository}"
RUNTIME_USER="${RUNTIME_USER:-alchemy}"
V1_CONTAINER="${V1_CONTAINER:-alchemy-media-agent}"
V2_UNITS=(alchemy-v2-api.service alchemy-v2-worker.service alchemy-v2-sync-worker.service)
compose_cmd=()

[[ "${TARGET_SHA}" =~ ^[0-9a-f]{40}$ ]] || { echo "TARGET_SHA must be a 40-character SHA" >&2; exit 2; }
for command in git python3 docker; do
  command -v "${command}" >/dev/null || { echo "${command} is required" >&2; exit 1; }
done

if docker compose version >/dev/null 2>&1; then
  compose_cmd=(docker compose)
elif command -v docker-compose >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
  compose_cmd=(docker-compose)
else
  echo "docker compose or docker-compose is required" >&2
  exit 1
fi

old_release="$(realpath "${DEPLOY_LINK}")"
live_env="$(docker inspect "${V1_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/app/.env"}}{{.Source}}{{end}}{{end}}')"
v1_media="$(docker inspect "${V1_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/app/.media_storage"}}{{.Source}}{{end}}{{end}}')"
v2_storage="$(docker inspect "${V1_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/alchemy/v2/storage"}}{{.Source}}{{end}}{{end}}')"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
candidate="${RELEASE_ROOT}/v3-release-governed-${stamp}-${TARGET_SHA:0:12}"
backup_dir="/var/backups/alchemy-v2-runtime-${stamp}"
rollback_tag="alchemy-media-agent:rollback-${stamp}"
switched=0
units_installed=0
old_image=""

wait_for_unit() {
  local unit="$1"
  for _ in $(seq 1 60); do
    systemctl is-active --quiet "${unit}" && return 0
    sleep 2
  done
  return 1
}

wait_for_http() {
  local url="$1"
  for _ in $(seq 1 60); do
    curl -fsS --max-time 3 "${url}" >/dev/null && return 0
    sleep 2
  done
  return 1
}

restore_units() {
  [[ "${units_installed}" == "1" ]] || return 0
  for unit in "${V2_UNITS[@]}"; do
    [[ -f "${backup_dir}/${unit}" ]] && install -m 644 "${backup_dir}/${unit}" "/etc/systemd/system/${unit}"
  done
  systemctl daemon-reload
}

rollback() {
  [[ "${switched}" == "1" ]] || return 0
  echo "ROLLBACK: restoring ${old_release}" >&2
  ln -sfn "${old_release}" "${DEPLOY_LINK}" || true
  restore_units || true
  if [[ -n "${old_image}" ]]; then
    docker tag "${old_image}" alchemy-media-agent:latest || true
  fi
  docker rm -f "${V1_CONTAINER}" >/dev/null 2>&1 || true
  if [[ -f "${old_release}/docker-compose.yml" ]]; then
    (
      cd "${old_release}"
      APP_PORT=8017 V2_API_PROXY_BASE_URL=http://127.0.0.1:8020 \
        V1_MEDIA_STORAGE_DIR="${v1_media}" V2_STORAGE_DIR="${v2_storage}" \
        "${compose_cmd[@]}" -f "${old_release}/docker-compose.yml" up -d --no-build "${V1_CONTAINER}"
    ) || true
  fi
  for unit in "${V2_UNITS[@]}"; do
    systemctl restart "${unit}" || true
  done
}

trap rollback ERR
mkdir -p "${RELEASE_ROOT}" "${backup_dir}"
[[ -f "${live_env}" && -d "${v1_media}" && -d "${v2_storage}" ]] || { echo "Alchemy storage mounts are incomplete" >&2; exit 1; }

if [[ -e "${REPOSITORY_ROOT}/.git" ]]; then
  git -C "${REPOSITORY_ROOT}" fetch --prune origin
else
  git clone --no-checkout "${REPO_URL}" "${REPOSITORY_ROOT}"
fi
git -C "${REPOSITORY_ROOT}" fetch --prune origin
git -C "${REPOSITORY_ROOT}" cat-file -e "${TARGET_SHA}^{commit}"
git -C "${REPOSITORY_ROOT}" worktree add --detach "${candidate}" "${TARGET_SHA}"
cp -p "${live_env}" "${candidate}/src_skeleton/.env"

for release in "${old_release}" "${candidate}"; do
  v2_dir="${release}/custom_media_agent_2_0"
  v2_python="${v2_dir}/.venv/bin/python"
  runtime_requirements="${candidate}/custom_media_agent_2_0/requirements.txt"
  [[ -f "${runtime_requirements}" ]] || { echo "V2 requirements missing: ${runtime_requirements}" >&2; exit 1; }
  [[ -x "${v2_python}" ]] || python3 -m venv "${v2_dir}/.venv"
  "${v2_python}" -m pip install --disable-pip-version-check --no-input --upgrade-strategy only-if-needed -r "${runtime_requirements}"
  "${v2_python}" -m pip check
  (cd "${v2_dir}" && "${v2_python}" -c 'import app.main; import httpx, httpcore')
done

install -d -m 755 /usr/local/lib/alchemy
install -m 755 "${candidate}/ops/vps-release/v2_runtime_guard.py" /usr/local/lib/alchemy/v2_runtime_guard.py
python3 "${candidate}/ops/vps-release/v2_runtime_guard.py" --release "${old_release}" --write-manifest
python3 "${candidate}/ops/vps-release/v2_runtime_guard.py" --release "${candidate}" --write-manifest
chown "${RUNTIME_USER}:${RUNTIME_USER}" "${old_release}/custom_media_agent_2_0/.alchemy-v2-runtime.json" "${candidate}/custom_media_agent_2_0/.alchemy-v2-runtime.json"
chown -R "${RUNTIME_USER}:${RUNTIME_USER}" "${old_release}/custom_media_agent_2_0/.venv" "${candidate}/custom_media_agent_2_0/.venv"
python3 "${candidate}/ops/vps-release/v2_runtime_guard.py" --release "${old_release}" --verify
python3 "${candidate}/ops/vps-release/v2_runtime_guard.py" --release "${candidate}" --verify

for unit in "${V2_UNITS[@]}"; do
  install -m 644 "/etc/systemd/system/${unit}" "${backup_dir}/${unit}"
done
old_image="$(docker inspect "${V1_CONTAINER}" --format '{{.Image}}')"
docker tag "${old_image}" "${rollback_tag}"
docker build -t alchemy-media-agent:latest -f "${candidate}/src_skeleton/Dockerfile" "${candidate}"

ln -sfn "${candidate}" "${DEPLOY_LINK}"
switched=1
for unit in "${V2_UNITS[@]}"; do
  template="${candidate}/custom_media_agent_2_0/deploy/systemd/${unit}"
  rendered="$(mktemp)"
  sed "s|__ALCHEMY_RELEASE_LINK__|${DEPLOY_LINK}|g" "${template}" > "${rendered}"
  install -m 644 "${rendered}" "/etc/systemd/system/${unit}"
  rm -f "${rendered}"
done
units_installed=1
systemctl daemon-reload

docker rm -f "${V1_CONTAINER}" >/dev/null 2>&1 || true
(
  cd "${candidate}"
  APP_PORT=8017 V2_API_PROXY_BASE_URL=http://127.0.0.1:8020 \
    V1_MEDIA_STORAGE_DIR="${v1_media}" V2_STORAGE_DIR="${v2_storage}" \
    "${compose_cmd[@]}" -f "${candidate}/docker-compose.yml" up -d --no-build "${V1_CONTAINER}"
)
for unit in "${V2_UNITS[@]}"; do
  systemctl restart "${unit}"
done
for unit in "${V2_UNITS[@]}"; do
  wait_for_unit "${unit}"
done
wait_for_http http://127.0.0.1:8017/healthz
wait_for_http http://127.0.0.1:8020/api/v2/health
wait_for_http https://alchemy.aiself.vip/api/v2/health

api_pid="$(systemctl show -p MainPID --value alchemy-v2-api.service)"
test -n "${api_pid}" -a "${api_pid}" != "0"
test "$(readlink -f "/proc/${api_pid}/cwd")" = "${candidate}/custom_media_agent_2_0"
runuser -u "${RUNTIME_USER}" -- "${candidate}/custom_media_agent_2_0/.venv/bin/python" -c 'import httpcore; print("httpcore=" + httpcore.__version__)'
body="$(mktemp)"
status="$(curl -sS -o "${body}" -w '%{http_code}' --max-time 25 -X POST http://127.0.0.1:8020/api/v2/veyra/login -H 'Content-Type: application/json' --data '{"ticket":"codex-invalid-diagnostic-ticket"}')"
if grep -q 'ModuleNotFoundError' "${body}"; then
  rm -f "${body}"
  exit 1
fi
rm -f "${body}"
test "${status}" != "500"
docker exec "${V1_CONTAINER}" sh -lc "grep -q 'function v3DedupeOutputItems' /app/app/static/app.js && grep -q 'function mobileV3DedupeOutputItems' /app/app/mobile_static/mobile.js"
test "$(docker inspect "${V1_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/app/.env"}}{{.Source}}{{end}}{{end}}')" = "${candidate}/src_skeleton/.env"

docker rmi "${rollback_tag}" >/dev/null 2>&1 || true
trap - ERR
echo "VPS_ALCHEMY_RELEASE_MIGRATED=${candidate}"
echo "VPS_ALCHEMY_VEYRA_INVALID_TICKET_STATUS=${status}"
echo "VPS_ALCHEMY_V2_RUNTIME_GUARD=active"
echo "VPS_ALCHEMY_SUB2API=untouched"
