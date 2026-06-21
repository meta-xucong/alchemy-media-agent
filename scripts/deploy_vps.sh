#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${REPO_URL:-https://github.com/meta-xucong/alchemy-media-agent.git}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/alchemy-media-agent}"
APP_PORT="${APP_PORT:-8017}"
V2_API_PROXY_BASE_URL="${V2_API_PROXY_BASE_URL:-http://127.0.0.1:8020}"
V2_STORAGE_DIR="${V2_STORAGE_DIR:-/var/lib/alchemy/v2/storage}"
V1_MEDIA_STORAGE_DIR="${V1_MEDIA_STORAGE_DIR:-/var/lib/alchemy/v1/media_storage}"
LOCAL_MODE=0
SKIP_ENV=0
INSTALL_DOCKER=1
V2_DIR=""

usage() {
  cat <<'USAGE'
Usage:
  scripts/deploy_vps.sh [--local] [--dir PATH] [--repo URL] [--skip-env] [--no-install-docker]

Environment:
  OPENAI_API_KEY             Required unless --skip-env is used
  ANTHROPIC_AUTH_TOKEN       Required unless --skip-env is used
  GITHUB_TOKEN               Optional for cloning this private repo from a fresh VPS
  APP_PORT                   Host port, defaults to 8017
  DEPLOY_DIR                 Deploy directory, defaults to /opt/alchemy-media-agent
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)
      LOCAL_MODE=1
      shift
      ;;
    --dir)
      DEPLOY_DIR="$2"
      shift 2
      ;;
    --repo)
      REPO_URL="$2"
      shift 2
      ;;
    --skip-env)
      SKIP_ENV=1
      shift
      ;;
    --no-install-docker)
      INSTALL_DOCKER=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

run_as_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "Need root privileges for: $*" >&2
    exit 1
  fi
}

ensure_command() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    return 1
  fi
}

install_docker_if_needed() {
  if ensure_command docker; then
    return
  fi
  if [[ "${INSTALL_DOCKER}" != "1" ]]; then
    echo "Docker is required." >&2
    exit 1
  fi
  if ! ensure_command apt-get; then
    echo "Auto-install only supports apt-based Linux. Install Docker and rerun." >&2
    exit 1
  fi
  run_as_root apt-get update
  local packages=(ca-certificates curl git docker.io)
  if apt-cache show docker-compose-plugin >/dev/null 2>&1; then
    packages+=(docker-compose-plugin)
  fi
  run_as_root apt-get install -y "${packages[@]}"
  run_as_root systemctl enable --now docker || true
}

ensure_deploy_tools() {
  local missing=()
  for tool in git curl; do
    if ! ensure_command "${tool}"; then
      missing+=("${tool}")
    fi
  done
  if [[ "${#missing[@]}" -eq 0 ]]; then
    return
  fi
  if ! ensure_command apt-get; then
    echo "Missing required tools: ${missing[*]}. Install them and rerun." >&2
    exit 1
  fi
  run_as_root apt-get update
  run_as_root apt-get install -y "${missing[@]}"
}

git_with_auth() {
  if [[ -n "${GITHUB_TOKEN:-}" && "${REPO_URL}" == https://github.com/* ]]; then
    git -c "http.https://github.com/.extraheader=AUTHORIZATION: bearer ${GITHUB_TOKEN}" "$@"
  else
    git "$@"
  fi
}

sync_repo() {
  if [[ "${LOCAL_MODE}" == "1" ]]; then
    DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    return
  fi

  if [[ -d "${DEPLOY_DIR}/.git" ]]; then
    git_with_auth -C "${DEPLOY_DIR}" fetch --prune origin
    git -C "${DEPLOY_DIR}" reset --hard origin/main
    return
  fi

  run_as_root mkdir -p "${DEPLOY_DIR}"
  if [[ ! -w "${DEPLOY_DIR}" ]]; then
    run_as_root chown -R "$(id -u):$(id -g)" "${DEPLOY_DIR}"
  fi
  git_with_auth clone "${REPO_URL}" "${DEPLOY_DIR}"
}

write_env_file() {
  if [[ "${SKIP_ENV}" == "1" ]]; then
    return
  fi
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "OPENAI_API_KEY is required. Pass it as an environment variable or use --skip-env with an existing src_skeleton/.env." >&2
    exit 1
  fi
  if [[ -z "${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
    echo "ANTHROPIC_AUTH_TOKEN is required. Pass it as an environment variable or use --skip-env with an existing src_skeleton/.env." >&2
    exit 1
  fi

  umask 077
  cat > "${DEPLOY_DIR}/src_skeleton/.env" <<EOF
MEDIA_AGENT_MODE=live
MOCK_IMAGE_PROVIDER_ENABLED=false
ORCHESTRATION_MODE=runtime_first

DEFAULT_IMAGE_PROVIDER=${DEFAULT_IMAGE_PROVIDER:-openai_gpt_image}
DEFAULT_IMAGE_MODEL=${DEFAULT_IMAGE_MODEL:-gpt-image-2}
OPENAI_IMAGE_MODEL=${OPENAI_IMAGE_MODEL:-gpt-image-2}
GEMINI_IMAGE_MODEL=${GEMINI_IMAGE_MODEL:-gemini-3-pro-image-preview}
GEMINI_IMAGE_BASE_URL=${GEMINI_IMAGE_BASE_URL:-}

DEFAULT_LLM_PROVIDER=${DEFAULT_LLM_PROVIDER:-anthropic}
DEFAULT_LLM_MODEL=${DEFAULT_LLM_MODEL:-kimi-for-coding}
BACKUP_LLM_PROVIDER=${BACKUP_LLM_PROVIDER:-openai}
BACKUP_LLM_MODEL=${BACKUP_LLM_MODEL:-gpt-5.5}
OPENAI_LLM_MODEL=${OPENAI_LLM_MODEL:-gpt-5.5}
KIMI_LLM_MODEL=${KIMI_LLM_MODEL:-kimi-for-coding}
LLM_PROMPT_PLANNING_ENABLED=${LLM_PROMPT_PLANNING_ENABLED:-true}
IMAGE_WORK_INTENSITY=${IMAGE_WORK_INTENSITY:-atelier}

DEFAULT_VIDEO_PROVIDER=${DEFAULT_VIDEO_PROVIDER:-seedance}

OPENAI_API_KEY=${OPENAI_API_KEY}
OPENAI_BASE_URL=${OPENAI_BASE_URL:-https://aiself.vip/v1}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
ANTHROPIC_AUTH_TOKEN=${ANTHROPIC_AUTH_TOKEN}
ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-https://aiself.vip}
GEMINI_IMAGE_API_KEY=${GEMINI_IMAGE_API_KEY:-}
BYTEPLUS_API_KEY=${BYTEPLUS_API_KEY:-}

MEDIA_STORAGE_ROOT=.media_storage
V2_API_PROXY_BASE_URL=${V2_API_PROXY_BASE_URL}
V2_STORAGE_DIR=${V2_STORAGE_DIR}
V1_MEDIA_STORAGE_DIR=${V1_MEDIA_STORAGE_DIR}
EOF
}

ensure_v1_media_storage() {
  run_as_root mkdir -p "${V1_MEDIA_STORAGE_DIR}"
  local media_sources=()
  if [[ -d "${DEPLOY_DIR}/src_skeleton/.media_storage" ]]; then
    media_sources+=("${DEPLOY_DIR}/src_skeleton/.media_storage")
  fi
  if [[ -d "${DEPLOY_DIR}-releases" ]]; then
    while IFS= read -r source_dir; do
      media_sources+=("${source_dir}")
    done < <(find "${DEPLOY_DIR}-releases" -mindepth 3 -maxdepth 3 -type d -path "*/src_skeleton/.media_storage" 2>/dev/null || true)
  fi
  for source_dir in "${media_sources[@]}"; do
    if command -v rsync >/dev/null 2>&1; then
      run_as_root rsync -a --ignore-existing "${source_dir}/" "${V1_MEDIA_STORAGE_DIR}/" || true
    else
      run_as_root cp -an "${source_dir}/." "${V1_MEDIA_STORAGE_DIR}/" 2>/dev/null || true
    fi
  done
  merge_v1_history_records "${media_sources[@]}"
  if [[ ! -w "${V1_MEDIA_STORAGE_DIR}" ]]; then
    run_as_root chown -R "$(id -u):$(id -g)" "${V1_MEDIA_STORAGE_DIR}" || true
  fi
}

merge_v1_history_records() {
  if [[ "$#" -eq 0 ]] || ! command -v python3 >/dev/null 2>&1; then
    return
  fi
  run_as_root env V1_MEDIA_STORAGE_DIR="${V1_MEDIA_STORAGE_DIR}" python3 - "$@" <<'PY'
import json
import os
import tempfile
from pathlib import Path

target = Path(os.environ["V1_MEDIA_STORAGE_DIR"]) / "history" / "outputs.jsonl"
sources = [Path(item) / "history" / "outputs.jsonl" for item in os.sys.argv[1:]]
records = {}
order = []

for path in [target, *sources]:
    if not path.exists():
        continue
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        output_id = str(record.get("id") or "").strip()
        if not output_id:
            continue
        if output_id not in records:
            order.append(output_id)
        records[output_id] = record

if not records:
    raise SystemExit(0)

target.parent.mkdir(parents=True, exist_ok=True)
fd, tmp_name = tempfile.mkstemp(prefix="outputs.", suffix=".jsonl", dir=str(target.parent))
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    for output_id in order:
        handle.write(json.dumps(records[output_id], ensure_ascii=False, separators=(",", ":")) + "\n")
os.replace(tmp_name, target)
PY
}

prepare_static_assets() {
  if ! command -v gzip >/dev/null 2>&1; then
    return
  fi
  local static_roots=(
    "${DEPLOY_DIR}/src_skeleton/app/static"
    "${DEPLOY_DIR}/src_skeleton/app/mobile_static"
  )
  for static_root in "${static_roots[@]}"; do
    [[ -d "${static_root}" ]] || continue
    find "${static_root}" -type f \( \
      -name '*.js' -o -name '*.css' -o -name '*.html' -o -name '*.svg' -o -name '*.json' \
    \) -size +1024c -print0 | while IFS= read -r -d '' file; do
      gzip -kf -9 "${file}"
    done
  done
}

start_stack() {
  cd "${DEPLOY_DIR}"
  ensure_v1_media_storage
  prepare_static_assets
  docker rm -f alchemy-media-agent >/dev/null 2>&1 || true
  if docker compose version >/dev/null 2>&1; then
    APP_PORT="${APP_PORT}" V2_API_PROXY_BASE_URL="${V2_API_PROXY_BASE_URL}" V2_STORAGE_DIR="${V2_STORAGE_DIR}" V1_MEDIA_STORAGE_DIR="${V1_MEDIA_STORAGE_DIR}" docker compose up -d --build --remove-orphans
    return
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    APP_PORT="${APP_PORT}" V2_API_PROXY_BASE_URL="${V2_API_PROXY_BASE_URL}" V2_STORAGE_DIR="${V2_STORAGE_DIR}" V1_MEDIA_STORAGE_DIR="${V1_MEDIA_STORAGE_DIR}" docker-compose up -d --build --remove-orphans
    return
  fi

  docker build -t alchemy-media-agent:latest ./src_skeleton
  local docker_run_args=(
    -d
    --name alchemy-media-agent
    --restart unless-stopped
    --network host
    --env-file ./src_skeleton/.env
    -e "V2_API_PROXY_BASE_URL=${V2_API_PROXY_BASE_URL}"
    -e "V2_STORAGE_DIR=${V2_STORAGE_DIR}"
    -e "V1_MEDIA_STORAGE_DIR=${V1_MEDIA_STORAGE_DIR}"
    -v "${DEPLOY_DIR}/src_skeleton/.env:/app/.env"
    -v "${V1_MEDIA_STORAGE_DIR}:/app/.media_storage"
  )
  if [[ -d "${V2_STORAGE_DIR}" ]]; then
    docker_run_args+=(-v "${V2_STORAGE_DIR}:${V2_STORAGE_DIR}:ro")
  fi
  docker run "${docker_run_args[@]}" \
    alchemy-media-agent:latest \
    python -m uvicorn app.main:app --host 127.0.0.1 --port "${APP_PORT}"
}

ensure_v2_runtime() {
  V2_DIR="${DEPLOY_DIR}/custom_media_agent_2_0"
  if [[ ! -d "${V2_DIR}" ]]; then
    return
  fi

  if ! ensure_command python3; then
    if ! ensure_command apt-get; then
      echo "python3 is required to prepare the V2 runtime." >&2
      exit 1
    fi
    run_as_root apt-get update
    run_as_root apt-get install -y python3 python3-venv python3-pip
  fi

  if [[ ! -x "${V2_DIR}/.venv/bin/python" ]]; then
    python3 -m venv "${V2_DIR}/.venv"
  fi
  "${V2_DIR}/.venv/bin/python" -m pip install --upgrade pip
  "${V2_DIR}/.venv/bin/python" -m pip install -r "${V2_DIR}/requirements.txt"

  if id alchemy >/dev/null 2>&1; then
    run_as_root chown -R alchemy:alchemy "${V2_DIR}/.venv"
  fi
}

restart_v2_services_if_present() {
  local units=(alchemy-v2-api.service alchemy-v2-worker.service alchemy-v2-sync-worker.service)
  local present=()
  for unit in "${units[@]}"; do
    if systemctl list-unit-files "${unit}" --no-legend 2>/dev/null | grep -q "${unit}"; then
      present+=("${unit}")
    fi
  done
  if [[ "${#present[@]}" -eq 0 ]]; then
    return
  fi
  run_as_root systemctl daemon-reload
  run_as_root systemctl restart "${present[@]}"
}

configure_nginx_if_present() {
  local nginx_conf="${DEPLOY_DIR}/alchemy-media-agent.nginx.conf"
  [[ -f "${nginx_conf}" ]] || return
  if ! command -v nginx >/dev/null 2>&1; then
    return
  fi
  local target_conf="/etc/nginx/conf.d/alchemy-media-agent.conf"
  if [[ -d "/etc/nginx/sites-available" ]]; then
    target_conf="/etc/nginx/sites-available/alchemy-media-agent"
    if [[ -d "/etc/nginx/sites-enabled" && ! -e "/etc/nginx/sites-enabled/alchemy-media-agent" ]]; then
      run_as_root ln -s "${target_conf}" "/etc/nginx/sites-enabled/alchemy-media-agent"
    fi
  fi
  if [[ "${target_conf}" != "/etc/nginx/conf.d/alchemy-media-agent.conf" && -f "/etc/nginx/conf.d/alchemy-media-agent.conf" ]]; then
    run_as_root rm -f "/etc/nginx/conf.d/alchemy-media-agent.conf"
  fi
  run_as_root cp "${nginx_conf}" "${target_conf}"
  if run_as_root nginx -t; then
    if command -v systemctl >/dev/null 2>&1; then
      run_as_root systemctl reload nginx || run_as_root nginx -s reload || true
    else
      run_as_root nginx -s reload || true
    fi
  else
    echo "nginx config test failed after installing ${target_conf}" >&2
    exit 1
  fi
}

health_check() {
  local url="http://127.0.0.1:${APP_PORT}/healthz"
  for _ in $(seq 1 30); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      echo "Alchemy Media Agent is running: http://127.0.0.1:${APP_PORT}/"
      return
    fi
    sleep 2
  done
  echo "Service did not pass health check. Recent logs:" >&2
  if docker compose version >/dev/null 2>&1; then
    docker compose -f "${DEPLOY_DIR}/docker-compose.yml" logs --tail=80 alchemy-media-agent >&2 || true
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose -f "${DEPLOY_DIR}/docker-compose.yml" logs --tail=80 alchemy-media-agent >&2 || true
  else
    docker logs --tail=80 alchemy-media-agent >&2 || true
  fi
  exit 1
}

install_docker_if_needed
ensure_deploy_tools
sync_repo
write_env_file
ensure_v2_runtime
start_stack
restart_v2_services_if_present
configure_nginx_if_present
health_check
